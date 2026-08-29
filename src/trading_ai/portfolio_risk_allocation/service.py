from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from math import isfinite, sqrt, log
from uuid import uuid4

from sqlalchemy import MetaData, Table, func, inspect, select
from sqlalchemy.exc import IntegrityError

from trading_ai.broker.ibkr.database_models import BrokerAccountSnapshotModel
from trading_ai.broker_portfolio_sync.models import (
    BrokerCurrentPositionModel,
    BrokerPortfolioPublicationModel,
)
from trading_ai.database.repositories.option_chain import OptionChainRepository
from trading_ai.market_intelligence.database_models import (
    SectorMembershipModel,
    SymbolReturnSnapshotModel,
)
from trading_ai.portfolio_management.database_models import PortfolioPositionModel
from trading_ai.portfolio_intelligence.models import ManagedPositionModel
from trading_ai.position_management.database_models import PositionExitInstructionModel

from .models import (
    PortfolioFitAssessmentModel,
    PortfolioRiskSnapshotModel,
    PortfolioStressSnapshotModel,
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, float(value)))


def number(value, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


class PortfolioRiskAllocationService:
    """Portfolio-level option risk, exposure, stress, and allocation analytics.

    Exact Polygon option quotes are preferred. Missing enrichment is retained as
    an explicit data-quality warning and receives conservative risk fallbacks.
    """

    POLICY_VERSION = "M64.2-GOVERNED-DEBIT-RISK-PRE-EXPIRATION-EXIT-1.0"
    SEMANTIC_FINGERPRINT_VERSION = (
        "M64.2.4.7-BASELINE-MATERIAL-RISK-AUTHORITY-1.0"
    )
    INTEGRITY_FINGERPRINT_VERSION = (
        "M64.2.4.7-EXACT-RISK-SNAPSHOT-INTEGRITY-1.0"
    )
    MATERIALITY_COMPARISON_VERSION = (
        "M64.2.4.7-BASELINE-RELATIVE-MATERIALITY-1.0"
    )
    MATERIALITY_POLICY = {
        "account_currency": 100.0,
        "position_currency": 1.0,
        "market_exposure_currency": 100.0,
        "risk_currency": 10.0,
        "percentage_points": 0.01,
        "portfolio_greek": 1.0,
        "beta_weighted_delta_currency": 100.0,
        "position_greek": 1.0,
        "option_price": 0.05,
        "underlying_price": 0.25,
        "volatility": 0.01,
        "beta": 0.01,
    }
    EXPIRATION_GUARD_SEMANTIC_FIELDS = (
        "label",
        "trigger_type",
        "trigger_value",
        "mandatory_exit",
        "governed_risk_basis",
        "m64_2",
        "trade_plan_id",
        "earliest_expiry",
        "exit_on_or_before_date",
        "minimum_trading_days_before_expiry",
        "execution_scope",
        "exit_method",
        "strategy_level_exit",
        "includes_short_legs",
        "leg_count",
        "management_generation",
        "armed_at",
        "activation_reason",
        "instruction_id",
        "status",
        "policy",
    )

    def __init__(self, session_factory):
        self.session_factory = session_factory

    @staticmethod
    def _canonical(value):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, dict):
            return {
                str(key): PortfolioRiskAllocationService._canonical(item)
                for key, item in sorted(
                    value.items(), key=lambda pair: str(pair[0])
                )
            }
        if isinstance(value, (list, tuple)):
            items = [
                PortfolioRiskAllocationService._canonical(item)
                for item in value
            ]
            return sorted(
                items,
                key=lambda item: json.dumps(
                    item,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ),
            )
        return value

    @staticmethod
    def _materiality_band(value, increment: float):
        if value is None:
            return None
        increment_decimal = Decimal(str(increment))
        band = (
            Decimal(str(number(value))) / increment_decimal
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        result = float(band * increment_decimal)
        return 0.0 if result == 0 else result

    @classmethod
    def _banded_mapping(cls, values: dict, increment: float) -> dict:
        return {
            str(key): cls._materiality_band(value, increment)
            for key, value in sorted((values or {}).items())
        }

    @staticmethod
    def _raw_number(value):
        return None if value is None else number(value)

    @classmethod
    def _project_number(
        cls,
        value,
        increment: float,
        *,
        apply_materiality_bands: bool,
    ):
        if apply_materiality_bands:
            return cls._materiality_band(value, increment)
        return cls._raw_number(value)

    @classmethod
    def _project_mapping(
        cls,
        values: dict,
        increment: float,
        *,
        apply_materiality_bands: bool,
    ) -> dict:
        return {
            str(key): cls._project_number(
                value,
                increment,
                apply_materiality_bands=apply_materiality_bands,
            )
            for key, value in sorted((values or {}).items())
        }

    @classmethod
    def _expiration_guard_projection(cls, guard: dict) -> dict:
        return {
            key: deepcopy(guard[key])
            for key in cls.EXPIRATION_GUARD_SEMANTIC_FIELDS
            if key in (guard or {})
        }

    @staticmethod
    def _position_identity(position: dict) -> dict:
        return {
            key: deepcopy(position.get(key))
            for key in (
                "symbol",
                "contract_id",
                "option_symbol",
                "managed_position_id",
                "security_type",
                "quantity",
                "multiplier",
                "expiry",
                "strike",
                "right",
            )
        }

    @classmethod
    def _position_key(cls, position: dict) -> str:
        stable = {
            key: deepcopy(position.get(key))
            for key in (
                "symbol",
                "contract_id",
                "option_symbol",
                "managed_position_id",
                "security_type",
                "expiry",
                "strike",
                "right",
            )
        }
        return json.dumps(
            cls._canonical(stable),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    @classmethod
    def _position_projection(
        cls,
        position: dict,
        *,
        apply_materiality_bands: bool,
    ) -> dict:
        policy = cls.MATERIALITY_POLICY
        projected = {
            **cls._position_identity(position),
            "strategy": position.get("strategy"),
            "sector": position.get("sector"),
            "industry": position.get("industry"),
            "theme": position.get("theme"),
            "lineage": deepcopy(position.get("lineage") or {}),
            "expiration_guard_armed": bool(
                position.get("expiration_guard_armed")
            ),
            "expiration_guard": cls._expiration_guard_projection(
                dict(position.get("expiration_guard") or {})
            ),
            "quote_quality": position.get("quote_quality"),
            "classification_quality": position.get(
                "classification_quality"
            ),
            "risk_method": position.get("risk_method"),
            "structure_id": position.get("structure_id"),
            "capital": {
                key: cls._project_number(
                    position.get(key),
                    policy["position_currency"],
                    apply_materiality_bands=apply_materiality_bands,
                )
                for key in (
                    "market_value",
                    "capital_committed",
                    "maximum_loss",
                    "managed_entry_value",
                    "structure_maximum_loss",
                    "structure_maximum_profit",
                )
                if key in position
            },
            "market_observation": {
                "option_mark": cls._project_number(
                    position.get("option_mark"),
                    policy["option_price"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "underlying_price": cls._project_number(
                    position.get("underlying_price"),
                    policy["underlying_price"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "implied_volatility": cls._project_number(
                    position.get("implied_volatility"),
                    policy["volatility"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "realized_volatility_20d": cls._project_number(
                    position.get("realized_volatility_20d"),
                    policy["volatility"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "beta": cls._project_number(
                    position.get("beta"),
                    policy["beta"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
            },
            "greeks": cls._project_mapping(
                dict(position.get("greeks") or {}),
                policy["position_greek"],
                apply_materiality_bands=apply_materiality_bands,
            ),
        }
        return projected

    @classmethod
    def _structure_projection(
        cls,
        structure: dict,
        positions: list[dict],
        *,
        apply_materiality_bands: bool,
    ) -> dict:
        legs = []
        for raw_index in structure.get("leg_indexes") or []:
            try:
                index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(positions):
                legs.append(cls._position_identity(positions[index]))
        return {
            key: deepcopy(structure.get(key))
            for key in (
                "structure_id",
                "symbol",
                "expiry",
                "strategy",
                "classification_quality",
            )
        } | {
            "legs": legs,
            "economics": {
                key: cls._project_number(
                    structure.get(key),
                    cls.MATERIALITY_POLICY["position_currency"],
                    apply_materiality_bands=apply_materiality_bands,
                )
                for key in (
                    "net_market_value",
                    "capital_committed",
                    "maximum_loss",
                    "maximum_profit",
                    "width",
                )
                if key in structure
            },
        }

    @classmethod
    def semantic_projection(
        cls,
        snapshot: dict,
        *,
        apply_materiality_bands: bool = True,
    ) -> dict:
        """Return the explicit, material risk authority projection.

        Structural portfolio, policy, capital, guard, classification, and data
        quality inputs are governed explicitly. Continuously recalculated market
        telemetry is placed into declared materiality bands. Raw payload fields
        cannot silently enter authority merely because a producer adds them.
        """
        policy = cls.MATERIALITY_POLICY
        payload = dict(snapshot.get("payload_json") or {})
        positions = [
            dict(position)
            for position in payload.get("positions") or []
            if isinstance(position, dict)
        ]
        aggregate_greeks = dict(payload.get("greeks") or {})
        beta_weighted_delta = aggregate_greeks.pop(
            "beta_weighted_delta", None
        )
        exposures = {
            str(dimension): cls._project_mapping(
                dict(values or {}),
                policy["market_exposure_currency"],
                apply_materiality_bands=apply_materiality_bands,
            )
            for dimension, values in sorted(
                dict(payload.get("exposures") or {}).items()
            )
        }
        capital = dict(payload.get("capital") or {})
        risk = dict(payload.get("risk") or {})
        stress = {
            str(name): cls._project_number(
                (details or {}).get("estimated_pnl"),
                policy["risk_currency"],
                apply_materiality_bands=apply_materiality_bands,
            )
            for name, details in sorted(
                dict(risk.get("stress") or {}).items()
            )
        }
        account_currency_fields = (
            "net_liquidation",
            "buying_power",
        )
        position_currency_fields = (
            "capital_committed",
            "open_risk",
        )
        percentage_fields = (
            "portfolio_heat_pct",
            "concentration_score",
            "diversification_score",
        )
        return cls._canonical({
            "version": cls.SEMANTIC_FINGERPRINT_VERSION,
            "policy_version": cls.POLICY_VERSION,
            "materiality_policy": cls.MATERIALITY_POLICY,
            "portfolio_id": snapshot.get("portfolio_id"),
            "status": snapshot.get("status"),
            "metrics": {
                **{
                    key: cls._project_number(
                        snapshot.get(key),
                        policy["account_currency"],
                        apply_materiality_bands=apply_materiality_bands,
                    )
                    for key in account_currency_fields
                },
                **{
                    key: cls._project_number(
                        snapshot.get(key),
                        policy["position_currency"],
                        apply_materiality_bands=apply_materiality_bands,
                    )
                    for key in position_currency_fields
                },
                **{
                    key: cls._project_number(
                        snapshot.get(key),
                        policy["risk_currency"],
                        apply_materiality_bands=apply_materiality_bands,
                    )
                    for key in ("var_95", "expected_shortfall_95")
                },
                **{
                    key: cls._project_number(
                        snapshot.get(key),
                        policy["percentage_points"],
                        apply_materiality_bands=apply_materiality_bands,
                    )
                    for key in percentage_fields
                },
                "health_score": cls._project_number(
                    snapshot.get("health_score"),
                    0.1,
                    apply_materiality_bands=apply_materiality_bands,
                ),
            },
            "position_count": payload.get("position_count"),
            "positions": {
                cls._position_key(position): cls._position_projection(
                    position,
                    apply_materiality_bands=apply_materiality_bands,
                )
                for position in positions
            },
            "structures": {
                str(structure.get("structure_id") or ""): (
                    cls._structure_projection(
                        structure,
                        positions,
                        apply_materiality_bands=apply_materiality_bands,
                    )
                )
                for structure in payload.get("structures") or []
                if isinstance(structure, dict)
            },
            "exposures": exposures,
            "greeks": {
                **cls._project_mapping(
                    aggregate_greeks,
                    policy["portfolio_greek"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "beta_weighted_delta": cls._project_number(
                    beta_weighted_delta,
                    policy["beta_weighted_delta_currency"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
            },
            "capital": {
                "net_liquidation": cls._project_number(
                    capital.get("net_liquidation"),
                    policy["account_currency"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "buying_power": cls._project_number(
                    capital.get("buying_power"),
                    policy["account_currency"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "market_value": cls._project_number(
                    capital.get("market_value"),
                    policy["market_exposure_currency"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "capital_committed": cls._project_number(
                    capital.get("capital_committed"),
                    policy["position_currency"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "open_risk": cls._project_number(
                    capital.get("open_risk"),
                    policy["position_currency"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "gross_leg_open_risk": cls._project_number(
                    capital.get("gross_leg_open_risk"),
                    policy["position_currency"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "capital_usage_pct": cls._project_number(
                    capital.get("capital_usage_pct"),
                    policy["percentage_points"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "portfolio_heat_pct": cls._project_number(
                    capital.get("portfolio_heat_pct"),
                    policy["percentage_points"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "trading_risk_basis": capital.get("trading_risk_basis"),
                "operational_risk": deepcopy(
                    capital.get("operational_risk") or {}
                ),
                "heat_risk_decomposition": deepcopy(
                    capital.get("heat_risk_decomposition") or {}
                ),
            },
            "risk": {
                "var_95_one_day": cls._project_number(
                    risk.get("var_95_one_day"),
                    policy["risk_currency"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "expected_shortfall_95_one_day": cls._project_number(
                    risk.get("expected_shortfall_95_one_day"),
                    policy["risk_currency"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "methodology": risk.get("methodology"),
                "concentration_hhi": cls._project_number(
                    risk.get("concentration_hhi"),
                    0.0001,
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "concentration_score": cls._project_number(
                    risk.get("concentration_score"),
                    policy["percentage_points"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "diversification_score": cls._project_number(
                    risk.get("diversification_score"),
                    policy["percentage_points"],
                    apply_materiality_bands=apply_materiality_bands,
                ),
                "stress": stress,
            },
            "data_quality": deepcopy(payload.get("data_quality") or {}),
            "limits": deepcopy(payload.get("limits") or {}),
        })

    @classmethod
    def materiality_projection(cls, snapshot: dict) -> dict:
        """Return exact governed values for baseline-relative comparison.

        The ordinary semantic fingerprint remains a compact immutable identity.
        No-op eligibility is decided here against the current published
        baseline so a sub-threshold change cannot become material merely by
        crossing a rounding boundary.
        """
        return cls.semantic_projection(
            snapshot,
            apply_materiality_bands=False,
        )

    @classmethod
    def _materiality_threshold(cls, path: tuple[str, ...]) -> float | None:
        policy = cls.MATERIALITY_POLICY
        if not path:
            return None
        root = path[0]
        leaf = path[-1]
        if root == "metrics":
            return {
                "net_liquidation": policy["account_currency"],
                "buying_power": policy["account_currency"],
                "capital_committed": policy["position_currency"],
                "open_risk": policy["position_currency"],
                "var_95": policy["risk_currency"],
                "expected_shortfall_95": policy["risk_currency"],
                "portfolio_heat_pct": policy["percentage_points"],
                "concentration_score": policy["percentage_points"],
                "diversification_score": policy["percentage_points"],
                "health_score": 0.1,
            }.get(leaf)
        if root == "positions" and len(path) >= 4:
            section = path[2]
            if section == "capital":
                return policy["position_currency"]
            if section == "greeks":
                return policy["position_greek"]
            if section == "market_observation":
                return {
                    "option_mark": policy["option_price"],
                    "underlying_price": policy["underlying_price"],
                    "implied_volatility": policy["volatility"],
                    "realized_volatility_20d": policy["volatility"],
                    "beta": policy["beta"],
                }.get(leaf)
        if root == "structures" and len(path) >= 4:
            if path[2] == "economics":
                return policy["position_currency"]
        if root == "exposures" and len(path) >= 3:
            return policy["market_exposure_currency"]
        if root == "greeks":
            if leaf == "beta_weighted_delta":
                return policy["beta_weighted_delta_currency"]
            return policy["portfolio_greek"]
        if root == "capital":
            if len(path) == 2:
                return {
                    "net_liquidation": policy["account_currency"],
                    "buying_power": policy["account_currency"],
                    "market_value": policy["market_exposure_currency"],
                    "capital_committed": policy["position_currency"],
                    "open_risk": policy["position_currency"],
                    "gross_leg_open_risk": policy["position_currency"],
                    "capital_usage_pct": policy["percentage_points"],
                    "portfolio_heat_pct": policy["percentage_points"],
                }.get(leaf)
            if path[1] == "heat_risk_decomposition" and leaf in {
                "gross_leg_risk",
                "governed_strategy_risk",
                "reconstructed_structure_risk",
                "standalone_risk",
                "netting_benefit",
                "maximum_loss",
                "trading_risk",
                "premium_paid",
            }:
                return policy["position_currency"]
        if root == "risk":
            if len(path) >= 3 and path[1] == "stress":
                return policy["risk_currency"]
            return {
                "var_95_one_day": policy["risk_currency"],
                "expected_shortfall_95_one_day": policy["risk_currency"],
                "concentration_hhi": 0.0001,
                "concentration_score": policy["percentage_points"],
                "diversification_score": policy["percentage_points"],
            }.get(leaf)
        if root == "data_quality" and leaf.endswith("_coverage_pct"):
            return policy["percentage_points"]
        return None

    @staticmethod
    def _materiality_path(path: tuple[str, ...]) -> str:
        if not path:
            return "$"
        rendered = "$"
        for part in path:
            if part.startswith("{"):
                rendered += f"[{part}]"
            else:
                rendered += f".{part}"
        return rendered

    @classmethod
    def materiality_evaluation(
        cls,
        baseline: dict,
        candidate: dict,
        *,
        detail_limit: int = 25,
    ) -> dict:
        """Compare a candidate with the sticky published risk baseline."""
        baseline_projection = cls.materiality_projection(baseline)
        candidate_projection = cls.materiality_projection(candidate)
        material_changes: list[dict] = []
        suppressed_changes: list[dict] = []
        material_count = 0
        structural_count = 0
        suppressed_count = 0

        def record(target: list[dict], payload: dict) -> None:
            if len(target) < max(0, int(detail_limit)):
                target.append(payload)

        def compare(before, after, path: tuple[str, ...]) -> None:
            nonlocal material_count, structural_count, suppressed_count
            if isinstance(before, dict) and isinstance(after, dict):
                before_keys = set(before)
                after_keys = set(after)
                for key in sorted(before_keys | after_keys):
                    next_path = (*path, str(key))
                    if key not in before or key not in after:
                        structural_count += 1
                        record(material_changes, {
                            "path": cls._materiality_path(next_path),
                            "change": "ADDED" if key not in before else "REMOVED",
                            "before": before.get(key),
                            "after": after.get(key),
                            "threshold": None,
                        })
                    else:
                        compare(before[key], after[key], next_path)
                return
            if isinstance(before, list) and isinstance(after, list):
                if len(before) != len(after):
                    structural_count += 1
                    record(material_changes, {
                        "path": cls._materiality_path(path),
                        "change": "LIST_LENGTH_CHANGED",
                        "before": len(before),
                        "after": len(after),
                        "threshold": None,
                    })
                    return
                for index, (left, right) in enumerate(zip(before, after)):
                    compare(left, right, (*path, str(index)))
                return
            numeric = (
                isinstance(before, (int, float))
                and not isinstance(before, bool)
                and isinstance(after, (int, float))
                and not isinstance(after, bool)
            )
            if numeric:
                left = float(before)
                right = float(after)
                if left == right:
                    return
                threshold = cls._materiality_threshold(path)
                delta = abs(right - left)
                finite = isfinite(left) and isfinite(right) and isfinite(delta)
                payload = {
                    "path": cls._materiality_path(path),
                    "before": left,
                    "after": right,
                    "absolute_delta": delta,
                    "threshold": threshold,
                }
                if threshold is None:
                    structural_count += 1
                    record(material_changes, {
                        **payload,
                        "change": "EXACT_NUMERIC_VALUE_CHANGED",
                    })
                elif finite and delta < threshold:
                    suppressed_count += 1
                    record(suppressed_changes, payload)
                else:
                    material_count += 1
                    record(material_changes, payload)
                return
            if type(before) is not type(after) or before != after:
                structural_count += 1
                record(material_changes, {
                    "path": cls._materiality_path(path),
                    "change": "EXACT_VALUE_CHANGED",
                    "before": before,
                    "after": after,
                    "threshold": None,
                })

        compare(baseline_projection, candidate_projection, ())
        equivalent = material_count == 0 and structural_count == 0
        return {
            "version": cls.MATERIALITY_COMPARISON_VERSION,
            "status": "EQUIVALENT" if equivalent else "MATERIAL_CHANGE",
            "equivalent": equivalent,
            "material_numeric_change_count": material_count,
            "structural_change_count": structural_count,
            "suppressed_submaterial_change_count": suppressed_count,
            "material_changes": material_changes,
            "suppressed_submaterial_changes": suppressed_changes,
        }

    @classmethod
    def resolve_material_authority(
        cls,
        candidate: dict,
        baseline: dict | None,
    ) -> dict:
        """Resolve the semantic identity used by an authority input contract."""
        candidate_payload = dict(candidate.get("payload_json") or {})
        candidate_semantic = cls.semantic_fingerprint(candidate)
        candidate_integrity = cls.state_integrity_fingerprint(candidate)
        candidate_valid = (
            candidate_payload.get("semantic_fingerprint") == candidate_semantic
            and candidate_payload.get("state_integrity_fingerprint")
            == candidate_integrity
        )
        result = {
            "version": cls.MATERIALITY_COMPARISON_VERSION,
            "status": "BASELINE_UNAVAILABLE",
            "candidate_integrity_valid": candidate_valid,
            "baseline_integrity_valid": False,
            "candidate_semantic_fingerprint": candidate_semantic,
            "effective_semantic_fingerprint": candidate_semantic,
            "baseline_snapshot_id": None,
            "reuse_published_semantics": False,
            "evaluation": None,
        }
        if not candidate_valid:
            result["status"] = "CANDIDATE_INTEGRITY_INVALID"
            return result
        if baseline is None:
            return result
        baseline_payload = dict(baseline.get("payload_json") or {})
        baseline_semantic = cls.semantic_fingerprint(baseline)
        baseline_integrity = cls.state_integrity_fingerprint(baseline)
        baseline_valid = (
            baseline_payload.get("semantic_fingerprint") == baseline_semantic
            and baseline_payload.get("state_integrity_fingerprint")
            == baseline_integrity
        )
        result.update({
            "baseline_snapshot_id": baseline.get("snapshot_id"),
            "baseline_integrity_valid": baseline_valid,
            "baseline_semantic_fingerprint": baseline_semantic,
        })
        if not baseline_valid:
            result["status"] = "BASELINE_INTEGRITY_INVALID"
            return result
        evaluation = cls.materiality_evaluation(baseline, candidate)
        result["evaluation"] = evaluation
        if evaluation["equivalent"]:
            result.update({
                "status": "BASELINE_EQUIVALENT",
                "effective_semantic_fingerprint": baseline_semantic,
                "reuse_published_semantics": True,
            })
        else:
            result["status"] = "MATERIAL_CHANGE"
        return result

    @classmethod
    def semantic_fingerprint(cls, snapshot: dict) -> str:
        projection = cls.semantic_projection(snapshot)
        return sha256(
            json.dumps(
                projection,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode()
        ).hexdigest()

    @classmethod
    def state_integrity_fingerprint(cls, snapshot: dict) -> str:
        """Hash the exact immutable snapshot independently of materiality."""
        exact = deepcopy(dict(snapshot))
        payload = deepcopy(dict(exact.get("payload_json") or {}))
        payload.pop("state_integrity_fingerprint", None)
        exact["payload_json"] = payload
        governed = {
            "version": cls.INTEGRITY_FINGERPRINT_VERSION,
            "snapshot": cls._canonical(exact),
        }
        return sha256(
            json.dumps(
                governed,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode()
        ).hexdigest()

    def build(
        self,
        portfolio_id: str = "PAPER-PRIMARY",
        actor: str = "m64-risk-engine",
        *,
        persist: bool = True,
    ):
        with self.session_factory() as session:
            broker_positions = list(
                session.scalars(
                    select(BrokerCurrentPositionModel).where(
                        BrokerCurrentPositionModel.portfolio_id == portfolio_id,
                        BrokerCurrentPositionModel.active.is_(True),
                    )
                ).all()
            )
            local_positions = list(
                session.scalars(
                    select(PortfolioPositionModel).where(
                        PortfolioPositionModel.portfolio_id == portfolio_id,
                        PortfolioPositionModel.status == "OPEN",
                    )
                ).all()
            )
            local_by_id = {row.position_id: row for row in local_positions}
            managed_positions = list(session.scalars(
                select(ManagedPositionModel).where(
                    ManagedPositionModel.portfolio_id == portfolio_id,
                    ManagedPositionModel.state.in_(("OPEN", "PARTIAL", "HEDGED", "ROLLED")),
                )
            ).all())
            managed_by_id = {row.position_id: row for row in managed_positions}
            managed_ids = list(managed_by_id)
            exit_instructions = list(session.scalars(
                select(PositionExitInstructionModel).where(
                    PositionExitInstructionModel.position_id.in_(managed_ids)
                )
            ).all()) if managed_ids else []
            active_guard_by_position = {}
            for instruction in exit_instructions:
                payload = dict(instruction.payload or {})
                if payload.get("label") != "EXPIRATION_GUARD_EXIT":
                    continue
                if str(instruction.status).upper() in {"FILLED", "CANCELLED", "CANCELED", "REJECTED", "FAILED", "SUPERSEDED", "COMPLETED"}:
                    continue
                active_guard_by_position[instruction.position_id] = instruction
            account = session.scalar(
                select(BrokerAccountSnapshotModel)
                .where(BrokerAccountSnapshotModel.portfolio_id == portfolio_id)
                .order_by(BrokerAccountSnapshotModel.captured_at.desc())
                .limit(1)
            )
            publication = session.scalar(
                select(BrokerPortfolioPublicationModel)
                .where(BrokerPortfolioPublicationModel.portfolio_id == portfolio_id)
                .order_by(BrokerPortfolioPublicationModel.published_at.desc())
                .limit(1)
            )

            net_liquidation = number(getattr(account, "net_liquidation", 0))
            buying_power = number(getattr(account, "buying_power", 0))
            greeks = defaultdict(float)
            beta_weighted_delta = 0.0
            exposures = {
                key: defaultdict(float)
                for key in (
                    "symbol",
                    "sector",
                    "industry",
                    "theme",
                    "strategy",
                    "asset_class",
                    "currency",
                    "dte_bucket",
                )
            }
            capital_committed = open_risk = market_value = 0.0
            position_rows: list[dict] = []
            warnings: list[str] = []
            exact_quotes = 0
            exact_classifications = 0
            timestamp = datetime.now(timezone.utc)

            for broker in broker_positions:
                local = local_by_id.get(broker.portfolio_position_id or "")
                managed = managed_by_id.get(str(getattr(broker, "managed_position_id", "") or ""))
                enrichment = self._enrich_position(session, broker, local, timestamp)
                if managed is not None:
                    enrichment["lineage"] = {
                        **dict(enrichment.get("lineage") or {}),
                        "managed_position_id": managed.position_id,
                        "trade_plan_id": managed.trade_plan_id,
                        "opportunity_id": managed.opportunity_id,
                    }
                    enrichment["strategy"] = str(managed.strategy or enrichment.get("strategy") or "UNKNOWN")
                    enrichment["classification_quality"] = "GOVERNED"
                if enrichment["quote_quality"] == "EXACT_POLYGON":
                    exact_quotes += 1
                else:
                    warnings.append(
                        f"{broker.symbol}:{broker.contract_id}: {enrichment['quote_quality']}"
                    )
                if enrichment["classification_quality"] == "GOVERNED":
                    exact_classifications += 1

                signed_quantity = number(broker.signed_quantity)
                multiplier = max(1.0, number(broker.multiplier, 1.0))
                abs_quantity = abs(signed_quantity)
                position_market_value = abs(enrichment["option_mark"] * multiplier * signed_quantity)
                if position_market_value <= 0:
                    position_market_value = abs(number(broker.market_value))
                position_capital = self._capital_committed(
                    broker, local, enrichment, abs_quantity, multiplier
                )
                maximum_loss = self._maximum_loss(
                    broker, local, enrichment, position_capital
                )
                market_value += position_market_value
                capital_committed += position_capital
                open_risk += maximum_loss

                position_greeks = {}
                for greek_name in ("delta", "gamma", "theta", "vega", "rho"):
                    unit_value = number(enrichment.get(greek_name))
                    aggregate_value = unit_value * signed_quantity * multiplier
                    greeks[greek_name] += aggregate_value
                    position_greeks[greek_name] = aggregate_value

                underlying_equivalent = (
                    position_greeks["delta"] * enrichment["underlying_price"]
                )
                beta_weighted_delta += underlying_equivalent * enrichment["beta"]

                labels = {
                    "symbol": broker.symbol,
                    "sector": enrichment["sector"],
                    "industry": enrichment["industry"],
                    "theme": enrichment["theme"],
                    "strategy": enrichment["strategy"],
                    "asset_class": broker.security_type,
                    "currency": broker.currency,
                    "dte_bucket": enrichment["dte_bucket"],
                }
                for dimension, label in labels.items():
                    exposures[dimension][label] += position_market_value

                position_rows.append(
                    {
                        "symbol": broker.symbol,
                        "contract_id": broker.contract_id,
                        "option_symbol": enrichment["option_symbol"],
                        "market_value": position_market_value,
                        "capital_committed": position_capital,
                        "maximum_loss": maximum_loss,
                        "strategy": enrichment["strategy"],
                        "sector": enrichment["sector"],
                        "industry": enrichment["industry"],
                        "theme": enrichment["theme"],
                        "lineage": enrichment["lineage"],
                        "managed_position_id": managed.position_id if managed is not None else None,
                        "managed_entry_value": number(managed.entry_value) if managed is not None else 0.0,
                        "expiration_guard_armed": bool(managed is not None and managed.position_id in active_guard_by_position),
                        "expiration_guard": dict(active_guard_by_position[managed.position_id].payload or {}) if managed is not None and managed.position_id in active_guard_by_position else {},
                        "security_type": broker.security_type,
                        "quantity": signed_quantity,
                        "multiplier": multiplier,
                        "expiry": broker.expiry,
                        "strike": broker.strike,
                        "right": broker.right,
                        "option_mark": enrichment["option_mark"],
                        "underlying_price": enrichment["underlying_price"],
                        "implied_volatility": enrichment["implied_volatility"],
                        "realized_volatility_20d": enrichment["realized_volatility_20d"],
                        "beta": enrichment["beta"],
                        "greeks": position_greeks,
                        "quote_quality": enrichment["quote_quality"],
                        "classification_quality": enrichment["classification_quality"],
                        "risk_method": enrichment["risk_method"],
                    }
                )

            structures = self._reconstruct_structures(position_rows)
            self._apply_structure_classification(position_rows, structures)
            # M64.1: portfolio heat must use strategy-level defined risk for reconstructed
            # multi-leg positions.  The legacy accumulator above is gross leg risk and
            # materially double-counts spreads/defined-risk structures.
            gross_leg_open_risk = open_risk
            open_risk, heat_risk_decomposition = self._strategy_netted_open_risk(position_rows, structures)
            operational_risk = self._expiration_operational_risk(managed_positions, active_guard_by_position, timestamp)
            # Rebuild strategy exposure after multi-leg reconstruction.
            exposures["strategy"] = defaultdict(float)
            for row in position_rows:
                exposures["strategy"][row["strategy"]] += row["market_value"]
            exact_classifications = sum(
                1 for row in position_rows
                if row["classification_quality"] in {"GOVERNED", "RECONSTRUCTED_MULTI_LEG"}
            )

            weights = [
                value / market_value for value in exposures["symbol"].values()
            ] if market_value else []
            hhi = sum(weight * weight for weight in weights)
            concentration = clamp(hhi * 100)
            diversification = clamp(100 - concentration)
            var95, expected_shortfall = self._delta_gamma_vega_var(position_rows)
            heat_pct = (open_risk / net_liquidation * 100) if net_liquidation else 0.0
            usage_pct = (
                capital_committed / net_liquidation * 100
            ) if net_liquidation else 0.0
            enrichment_coverage = (
                exact_quotes / len(broker_positions) * 100 if broker_positions else 0.0
            )
            classification_coverage = (
                exact_classifications / len(broker_positions) * 100
                if broker_positions else 0.0
            )
            health = clamp(
                100
                - max(0, heat_pct - 10) * 2
                - concentration * 0.25
                - max(0, usage_pct - 50) * 0.5
                - max(0, 100 - enrichment_coverage) * 0.15
            )
            stress = self._stress_payload(position_rows, market_value)
            status = (
                "READY"
                if broker_positions and enrichment_coverage == 100
                else "DEGRADED"
            )
            payload = {
                "policy_version": self.POLICY_VERSION,
                "generated_by": actor,
                "position_count": len(broker_positions),
                "greeks": {
                    **dict(greeks),
                    "beta_weighted_delta": beta_weighted_delta,
                },
                "exposures": {
                    key: dict(value) for key, value in exposures.items()
                },
                "capital": {
                    "net_liquidation": net_liquidation,
                    "buying_power": buying_power,
                    "market_value": market_value,
                    "capital_committed": capital_committed,
                    "capital_usage_pct": usage_pct,
                    "open_risk": open_risk,
                    "gross_leg_open_risk": gross_leg_open_risk,
                    "trading_risk_basis": "GOVERNED_PRE_EXPIRATION_DEFINED_LOSS",
                    "operational_risk": operational_risk,
                    "portfolio_heat_pct": heat_pct,
                    "heat_risk_decomposition": heat_risk_decomposition,
                },
                "risk": {
                    "var_95_one_day": var95,
                    "expected_shortfall_95_one_day": expected_shortfall,
                    "methodology": "DELTA_GAMMA_VEGA_1D_PROXY",
                    "concentration_hhi": hhi,
                    "concentration_score": concentration,
                    "diversification_score": diversification,
                    "stress": stress,
                },
                "data_quality": {
                    "exact_option_quote_coverage_pct": enrichment_coverage,
                    "governed_classification_coverage_pct": classification_coverage,
                    "warnings": warnings,
                    "structure_count": len(structures),
                    "multi_leg_position_count": sum(len(item["leg_indexes"]) for item in structures),
                },
                "structures": structures,
                "positions": position_rows,
                "limits": {
                    "max_symbol_pct": 10,
                    "max_sector_pct": 25,
                    "max_strategy_pct": 35,
                    "max_portfolio_heat_pct": 20,
                    "risk_per_trade_pct": 2,
                },
            }
            candidate = {
                "snapshot_id": "M64-RISK-" + uuid4().hex.upper(),
                "portfolio_id": portfolio_id,
                "snapshot_timestamp": now(),
                "broker_publication_id": getattr(publication, "publication_id", None),
                "status": status,
                "health_score": health,
                "net_liquidation": net_liquidation,
                "buying_power": buying_power,
                "capital_committed": capital_committed,
                "open_risk": open_risk,
                "var_95": var95,
                "expected_shortfall_95": expected_shortfall,
                "portfolio_heat_pct": heat_pct,
                "concentration_score": concentration,
                "diversification_score": diversification,
                "payload_json": payload,
            }
            payload["semantic_fingerprint"] = self.semantic_fingerprint(candidate)
            payload["state_integrity_fingerprint"] = (
                self.state_integrity_fingerprint(candidate)
            )
            snapshot = PortfolioRiskSnapshotModel(
                **candidate,
            )
            if persist:
                session.add(snapshot)
                session.commit()
            return self.serialize(snapshot)

    def persist(self, snapshot: dict) -> dict:
        """Persist a previously computed governed risk candidate exactly once."""
        values = {
            column.name: snapshot[column.name]
            for column in PortfolioRiskSnapshotModel.__table__.columns
        }
        with self.session_factory() as session:
            existing = session.get(
                PortfolioRiskSnapshotModel,
                str(values["snapshot_id"]),
            )
            if existing is not None:
                if existing.portfolio_id != values["portfolio_id"]:
                    raise RuntimeError("Risk snapshot identity belongs to another portfolio")
                return self.serialize(existing)
            row = PortfolioRiskSnapshotModel(**values)
            session.add(row)
            session.commit()
            return self.serialize(row)

    def _enrich_position(self, session, broker, local, timestamp: datetime) -> dict:
        expiry_date = None
        try:
            expiry_date = date.fromisoformat(str(broker.expiry)[:10]) if broker.expiry else None
        except ValueError:
            pass
        option_type = "CALL" if str(broker.right).upper().startswith("C") else "PUT"
        quote = None
        if expiry_date and broker.strike is not None:
            chain = OptionChainRepository(session).get_latest_snapshot(
                broker.symbol, timestamp.date()
            )
            target_strike = number(broker.strike)
            for candidate in chain:
                candidate_type = str(candidate.get("option_type") or "").upper()
                candidate_expiry = candidate.get("expiry")
                if hasattr(candidate_expiry, "isoformat"):
                    candidate_expiry = candidate_expiry.isoformat()
                if (
                    candidate_type in {option_type, option_type[0]}
                    and str(candidate_expiry)[:10] == expiry_date.isoformat()
                    and abs(number(candidate.get("strike")) - target_strike) < 1e-6
                ):
                    quote = candidate
                    break
        membership = session.scalar(
            select(SectorMembershipModel)
            .where(
                func.upper(SectorMembershipModel.symbol) == broker.symbol.upper(),
                SectorMembershipModel.is_active.is_(True),
            )
            .order_by(SectorMembershipModel.effective_from.desc())
            .limit(1)
        )
        returns = session.scalar(
            select(SymbolReturnSnapshotModel)
            .where(func.upper(SymbolReturnSnapshotModel.symbol) == broker.symbol.upper())
            .order_by(SymbolReturnSnapshotModel.snapshot_timestamp.desc())
            .limit(1)
        )
        latest_underlying_price = 0.0
        computed_rv = 0.0
        computed_beta = 0.0
        inspector = inspect(session.get_bind())
        if "price_history" in inspector.get_table_names():
            price_table = Table("price_history", MetaData(), autoload_with=session.get_bind())
            latest_underlying_price = number(session.execute(
                select(price_table.c.close)
                .where(func.upper(price_table.c.symbol) == broker.symbol.upper())
                .order_by(price_table.c.date.desc())
                .limit(1)
            ).scalar_one_or_none())
            computed_rv, computed_beta = self._market_metrics(
                session, price_table, broker.symbol.upper(), "SPY"
            )

        local_strategy = str(getattr(local, "strategy_type", "") or "")
        metadata = dict(getattr(local, "metadata_json", {}) or {})
        lineage_keys = (
            "decision_snapshot_id", "decision_state_hash", "trade_plan_id",
            "execution_intent_id", "opportunity_id", "management_snapshot_id",
        )
        lineage = {key: metadata.get(key) for key in lineage_keys if metadata.get(key)}
        source_artifact = str(getattr(local, "source_artifact", "") or "")
        governed_lineage = bool(lineage) or "M62" in source_artifact.upper() or str(getattr(broker, "provenance", "")).upper() == "INSTITUTIONAL_OPTIONS"
        generic = {"", "BROKER_SYNCED_OPTION", "BROKER_POSITION", "UNKNOWN"}
        if local_strategy not in generic:
            strategy = local_strategy
            classification_quality = "GOVERNED" if governed_lineage else "GOVERNED_LOCAL_STRATEGY"
        else:
            side = "LONG" if number(broker.signed_quantity) > 0 else "SHORT"
            strategy = f"{side}_{option_type}"
            classification_quality = "GOVERNED" if governed_lineage else "INFERRED_SINGLE_LEG"

        option_mark = 0.0
        quote_quality = "BROKER_FALLBACK"
        if quote is not None:
            bid = number(quote.get("bid"))
            ask = number(quote.get("ask"))
            option_mark = number(quote.get("mid")) or ((bid + ask) / 2 if bid > 0 and ask >= bid else 0)
            option_mark = option_mark or number(quote.get("last"))
            quote_quality = "EXACT_POLYGON"
        if option_mark <= 0:
            broker_market = number(broker.market_price)
            multiplier = max(1.0, number(broker.multiplier, 1.0))
            option_mark = broker_market / multiplier if broker_market > 20 else broker_market
            option_mark = option_mark or number(broker.average_cost) / multiplier

        expiry_days = (expiry_date - timestamp.date()).days if expiry_date else 0
        dte_bucket = (
            "0-7" if expiry_days <= 7 else
            "8-30" if expiry_days <= 30 else
            "31-60" if expiry_days <= 60 else
            "61-120" if expiry_days <= 120 else "121+"
        )
        return {
            "option_symbol": str((quote or {}).get("contract_ticker") or broker.local_symbol or ""),
            "option_mark": option_mark,
            "underlying_price": latest_underlying_price,
            "implied_volatility": number((quote or {}).get("implied_volatility")),
            "realized_volatility_20d": number(getattr(returns, "realized_volatility_20d", 0)) or computed_rv,
            "beta": number(getattr(returns, "beta_60d", 0)) or computed_beta or 1.0,
            "delta": number((quote or {}).get("delta")),
            "gamma": number((quote or {}).get("gamma")),
            "theta": number((quote or {}).get("theta")),
            "vega": number((quote or {}).get("vega")),
            "rho": number((quote or {}).get("rho")),
            "sector": str(getattr(membership, "sector", "UNKNOWN") or "UNKNOWN"),
            "industry": self._industry_label(
                broker.symbol,
                str(getattr(membership, "sector", "UNKNOWN") or "UNKNOWN"),
                str(getattr(membership, "industry", "UNKNOWN") or "UNKNOWN"),
            ),
            "theme": self._theme_label(broker.symbol, str(getattr(membership, "sector", "UNKNOWN") or "UNKNOWN")),
            "lineage": lineage,
            "strategy": strategy,
            "classification_quality": classification_quality,
            "quote_quality": quote_quality,
            "dte_bucket": dte_bucket,
            "risk_method": "LONG_PREMIUM" if number(broker.signed_quantity) > 0 else "SHORT_OPTION_CONSERVATIVE",
        }

    def _capital_committed(self, broker, local, enrichment, quantity, multiplier) -> float:
        local_value = number(getattr(local, "capital_committed", 0))
        if local_value > 0 and str(getattr(local, "strategy_type", "")) not in {
            "BROKER_SYNCED_OPTION", "BROKER_POSITION", "UNKNOWN", ""
        }:
            return local_value
        average_cost = abs(number(broker.average_cost))
        # IBKR option averageCost is commonly already expressed per contract.
        if broker.security_type == "OPT" and average_cost > enrichment["option_mark"] * 10:
            return average_cost * quantity
        return max(0.0, average_cost * quantity * multiplier)

    def _maximum_loss(self, broker, local, enrichment, committed) -> float:
        local_loss = number(getattr(local, "maximum_loss", 0))
        if local_loss > 0 and enrichment["classification_quality"] == "GOVERNED":
            return local_loss
        if number(broker.signed_quantity) > 0:
            return committed
        underlying = enrichment["underlying_price"]
        if enrichment["strategy"] == "SHORT_PUT" and underlying > 0:
            return max(committed, number(broker.strike) * max(1.0, number(broker.multiplier)) * abs(number(broker.signed_quantity)))
        return max(committed, underlying * max(1.0, number(broker.multiplier)) * abs(number(broker.signed_quantity)))

    def _delta_gamma_vega_var(self, rows: list[dict]) -> tuple[float, float]:
        variance = 0.0
        convexity_buffer = 0.0
        volatility_buffer = 0.0
        for row in rows:
            rv = row["realized_volatility_20d"] or row["implied_volatility"] or 0.30
            daily_vol = max(0.005, rv / sqrt(252))
            underlying = row["underlying_price"] or max(1.0, row["market_value"])
            delta_exposure = row["greeks"]["delta"] * underlying
            variance += (delta_exposure * daily_vol) ** 2
            convexity_buffer += abs(row["greeks"]["gamma"]) * (underlying * daily_vol) ** 2 * 0.5
            volatility_buffer += abs(row["greeks"]["vega"]) * max(0.01, row["implied_volatility"] * 0.10)
        sigma = sqrt(variance) + convexity_buffer + volatility_buffer
        return 1.65 * sigma, 2.06 * sigma

    def _stress_payload(self, rows: list[dict], market_value: float) -> dict:
        def scenario(price_shock: float = 0.0, iv_shock: float = 0.0, sector: str | None = None, spread_cost: float = 0.0):
            pnl = 0.0
            for row in rows:
                if sector and row["sector"].upper() != sector.upper():
                    continue
                spot = row["underlying_price"] or 0.0
                move = spot * price_shock
                pnl += row["greeks"]["delta"] * move
                pnl += 0.5 * row["greeks"]["gamma"] * move * move
                pnl += row["greeks"]["vega"] * iv_shock
                pnl -= row["market_value"] * spread_cost
            return {"estimated_pnl": pnl}

        scenarios = {
            "SPY_DOWN_5": scenario(price_shock=-0.05),
            "TECH_DOWN_10": scenario(price_shock=-0.10, sector="INFORMATION TECHNOLOGY"),
            "FINANCIALS_DOWN_8": scenario(price_shock=-0.08, sector="FINANCIALS"),
            "ENERGY_DOWN_10": scenario(price_shock=-0.10, sector="ENERGY"),
            "CONSUMER_STAPLES_DOWN_5": scenario(price_shock=-0.05, sector="CONSUMER STAPLES"),
            "VIX_UP_20": scenario(iv_shock=0.20),
            "VOLATILITY_CRUSH_15": scenario(iv_shock=-0.15),
            "RATES_UP_1": {
                "estimated_pnl": sum(row["greeks"]["rho"] * 0.01 for row in rows)
            },
            "LIQUIDITY_SHOCK": scenario(spread_cost=0.05),
            "CORRELATION_BREAKDOWN": scenario(price_shock=-0.04, iv_shock=0.10, spread_cost=0.03),
            "DEALER_UNWIND": scenario(price_shock=-0.06, iv_shock=0.12),
            "JOINT_EQUITY_IV_SHOCK": scenario(price_shock=-0.07, iv_shock=0.15),
        }
        return scenarios

    def _market_metrics(self, session, price_table, symbol: str, benchmark: str) -> tuple[float, float]:
        def closes(ticker: str, limit: int = 70) -> list[float]:
            rows = session.execute(
                select(price_table.c.close)
                .where(func.upper(price_table.c.symbol) == ticker)
                .order_by(price_table.c.date.desc())
                .limit(limit)
            ).scalars().all()
            return [number(value) for value in reversed(rows) if number(value) > 0]

        asset = closes(symbol)
        bench = closes(benchmark)
        asset_returns = [log(asset[i] / asset[i - 1]) for i in range(1, len(asset)) if asset[i - 1] > 0]
        rv_window = asset_returns[-20:]
        rv = sqrt(252) * sqrt(sum((x - sum(rv_window) / len(rv_window)) ** 2 for x in rv_window) / max(1, len(rv_window) - 1)) if len(rv_window) >= 2 else 0.0
        count = min(len(asset), len(bench), 61)
        beta = 0.0
        if count >= 21:
            ar = [log(asset[-count + i] / asset[-count + i - 1]) for i in range(1, count)]
            br = [log(bench[-count + i] / bench[-count + i - 1]) for i in range(1, count)]
            am, bm = sum(ar) / len(ar), sum(br) / len(br)
            covariance = sum((a - am) * (b - bm) for a, b in zip(ar, br)) / max(1, len(ar) - 1)
            variance = sum((b - bm) ** 2 for b in br) / max(1, len(br) - 1)
            beta = covariance / variance if variance > 1e-12 else 0.0
        return rv, beta

    def _industry_label(self, symbol: str, sector: str, industry: str) -> str:
        if industry and industry.upper() != "UNKNOWN":
            return industry
        overrides = {
            "WFC": "Diversified Banks", "XOM": "Integrated Oil & Gas",
            "KO": "Beverages", "USO": "Commodity ETF - Crude Oil",
        }
        if symbol.upper() in overrides:
            return overrides[symbol.upper()]
        sector_defaults = {
            "FINANCIALS": "Financial Services", "ENERGY": "Energy",
            "CONSUMER STAPLES": "Consumer Staples", "CRUDE OIL": "Commodity ETF",
            "INFORMATION TECHNOLOGY": "Technology",
        }
        return sector_defaults.get(sector.upper(), "UNKNOWN")

    def _theme_label(self, symbol: str, sector: str) -> str:
        overrides = {"USO": "Crude Oil", "XOM": "Energy", "WFC": "US Banks", "KO": "Defensive Consumer"}
        return overrides.get(symbol.upper(), sector if sector.upper() != "UNKNOWN" else "UNCLASSIFIED")

    def _reconstruct_structures(self, rows: list[dict]) -> list[dict]:
        groups: dict[tuple, list[int]] = defaultdict(list)
        for index, row in enumerate(rows):
            groups[(row["symbol"], row["expiry"], row["right"])].append(index)
        structures: list[dict] = []
        used: set[int] = set()
        for (symbol, expiry, right), indexes in groups.items():
            longs = sorted([i for i in indexes if rows[i]["quantity"] > 0], key=lambda i: number(rows[i]["strike"]))
            shorts = sorted([i for i in indexes if rows[i]["quantity"] < 0], key=lambda i: number(rows[i]["strike"]))
            for long_i in longs:
                if long_i in used:
                    continue
                match = next((i for i in shorts if i not in used and abs(abs(rows[i]["quantity"]) - abs(rows[long_i]["quantity"])) < 1e-9), None)
                if match is None:
                    continue
                long_strike, short_strike = number(rows[long_i]["strike"]), number(rows[match]["strike"])
                if right == "C":
                    strategy = "BULL_CALL_SPREAD" if long_strike < short_strike else "BEAR_CALL_SPREAD"
                else:
                    strategy = "BEAR_PUT_SPREAD" if long_strike > short_strike else "BULL_PUT_SPREAD"
                multiplier = max(number(rows[long_i]["multiplier"], 100), number(rows[match]["multiplier"], 100))
                quantity = min(abs(rows[long_i]["quantity"]), abs(rows[match]["quantity"]))
                width = abs(short_strike - long_strike) * multiplier * quantity
                net_market_value = rows[long_i]["market_value"] - rows[match]["market_value"]
                net_capital = max(0.0, rows[long_i]["capital_committed"] - rows[match]["capital_committed"])
                maximum_loss = net_capital if strategy in {"BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"} else max(0.0, width - abs(net_capital))
                maximum_profit = max(0.0, width - maximum_loss)
                structure_id = f"{symbol}:{expiry}:{right}:{long_strike:g}-{short_strike:g}"
                structures.append({
                    "structure_id": structure_id, "symbol": symbol, "expiry": expiry,
                    "strategy": strategy, "leg_indexes": [long_i, match],
                    "net_market_value": net_market_value, "capital_committed": net_capital,
                    "maximum_loss": maximum_loss, "maximum_profit": maximum_profit,
                    "width": width, "classification_quality": "RECONSTRUCTED_MULTI_LEG",
                })
                used.update({long_i, match})
        return structures

    def _apply_structure_classification(self, rows: list[dict], structures: list[dict]) -> None:
        for structure in structures:
            for index in structure["leg_indexes"]:
                rows[index]["strategy"] = structure["strategy"]
                rows[index]["classification_quality"] = "RECONSTRUCTED_MULTI_LEG"
                rows[index]["structure_id"] = structure["structure_id"]
                rows[index]["structure_maximum_loss"] = structure["maximum_loss"]
                rows[index]["structure_maximum_profit"] = structure["maximum_profit"]

    DEBIT_DEFINED_STRATEGIES = {
        "LONG_CALL", "LONG_PUT", "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD",
        "CALL_CALENDAR", "PUT_CALENDAR", "CALL_DIAGONAL", "PUT_DIAGONAL",
        "LONG_STRADDLE", "LONG_STRANGLE",
    }

    def _governed_debit_risk(self, rows: list[dict], indexes: list[int]) -> tuple[float | None, str]:
        group=[rows[i] for i in indexes]
        strategy=str(next((x.get("strategy") for x in group if x.get("strategy")), "UNKNOWN") or "UNKNOWN").upper()
        guards=[bool(x.get("expiration_guard_armed")) for x in group if x.get("managed_position_id")]
        guard_armed=bool(guards) and all(guards)
        if strategy not in self.DEBIT_DEFINED_STRATEGIES or not guard_armed:
            return None, "LEGACY_DEFINED_MAX_LOSS"
        managed_entries=[max(0.0,number(x.get("managed_entry_value"))) for x in group]
        entry=max(managed_entries or [0.0])
        if entry>0:
            return entry, "MANAGED_POSITION_NET_DEBIT_PREMIUM_PAID"
        net_debit=sum((1.0 if number(x.get("quantity"))>0 else -1.0)*max(0.0,number(x.get("capital_committed"))) for x in group)
        if net_debit>0:
            return net_debit, "BROKER_NET_DEBIT_PREMIUM_PAID"
        return None, "LEGACY_DEFINED_MAX_LOSS"

    def _strategy_netted_open_risk(self, rows: list[dict], structures: list[dict]) -> tuple[float, dict]:
        """M64.2 governed trading risk.

        Debit strategies with an armed mandatory pre-expiration full-strategy exit use
        the actual governed net debit/premium paid as trading capital at risk. Credit
        structures continue to use defined maximum loss; operational expiry/assignment
        risk is measured separately and never hidden inside portfolio heat.
        """
        consumed:set[int]=set();lineage_groups:dict[str,list[int]]=defaultdict(list)
        for index,row in enumerate(rows or []):
            lineage=dict(row.get("lineage") or {})
            key=str(row.get("managed_position_id") or lineage.get("trade_plan_id") or lineage.get("opportunity_id") or "")
            if key:lineage_groups[key].append(index)
        governed_strategy_risk=0.0;governed_groups=[]
        for key,indexes in lineage_groups.items():
            if not indexes:continue
            premium_risk,risk_basis=self._governed_debit_risk(rows,indexes)
            risks=[max(0.0,number(rows[i].get("maximum_loss"))) for i in indexes]
            risk=premium_risk if premium_risk is not None else (max(risks) if risks else 0.0)
            if risk<=0:continue
            consumed.update(indexes);governed_strategy_risk+=risk
            sample=rows[indexes[0]]
            governed_groups.append({
                "lineage_key":key,"managed_position_id":sample.get("managed_position_id"),
                "symbol":sample.get("symbol"),"strategy":sample.get("strategy"),
                "maximum_loss":risk,"trading_risk":risk,"risk_basis":risk_basis,
                "premium_paid":max([number(rows[i].get("managed_entry_value")) for i in indexes] or [0.0]),
                "expiration_guard_armed":all(bool(rows[i].get("expiration_guard_armed")) for i in indexes),
                "leg_count":len(indexes),"netting_basis":"GOVERNED_MANAGED_POSITION",
            })
        reconstructed_risk=0.0;structure_details=[]
        for structure in structures or []:
            indexes=[int(i) for i in (structure.get("leg_indexes") or [])]
            if any(i in consumed for i in indexes):continue
            risk=max(0.0,number(structure.get("maximum_loss")));reconstructed_risk+=risk;consumed.update(indexes)
            structure_details.append({"structure_id":structure.get("structure_id"),"symbol":structure.get("symbol"),"strategy":structure.get("strategy"),"maximum_loss":risk,"trading_risk":risk,"risk_basis":"RECONSTRUCTED_DEFINED_MAX_LOSS","leg_count":len(indexes),"netting_basis":"RECONSTRUCTED_SAME_EXPIRY_STRUCTURE"})
        standalone_risk=0.0;standalone_count=0;standalone_details=[]
        for index,row in enumerate(rows or []):
            if index in consumed:continue
            premium_risk,risk_basis=self._governed_debit_risk(rows,[index])
            risk=premium_risk if premium_risk is not None else max(0.0,number(row.get("maximum_loss")))
            standalone_risk+=risk;standalone_count+=1
            standalone_details.append({"symbol":row.get("symbol"),"strategy":row.get("strategy"),"managed_position_id":row.get("managed_position_id"),"trading_risk":risk,"risk_basis":risk_basis,"expiration_guard_armed":bool(row.get("expiration_guard_armed"))})
        total=governed_strategy_risk+reconstructed_risk+standalone_risk
        gross=sum(max(0.0,number(row.get("maximum_loss"))) for row in rows or [])
        return total,{
            "methodology":"M64_2_GOVERNED_DEBIT_PREMIUM_THEN_DEFINED_MAX_LOSS",
            "gross_leg_risk":gross,"governed_strategy_risk":governed_strategy_risk,
            "reconstructed_structure_risk":reconstructed_risk,"standalone_risk":standalone_risk,
            "netted_leg_count":len(consumed),"standalone_leg_count":standalone_count,
            "governed_group_count":len(governed_groups),"reconstructed_structure_count":len(structure_details),
            "netting_benefit":max(0.0,gross-total),"governed_groups":governed_groups,
            "reconstructed_structures":structure_details,"standalone_positions":standalone_details,
        }

    def _expiration_operational_risk(self, managed_positions, active_guard_by_position, timestamp:datetime)->dict:
        total=len(managed_positions or []);missing=[];due=[];armed=0;nearest=None
        today=timestamp.date()
        for p in managed_positions or []:
            guard=active_guard_by_position.get(p.position_id)
            if guard is None:
                missing.append({"position_id":p.position_id,"symbol":p.symbol,"strategy":p.strategy})
                continue
            armed+=1;payload=dict(guard.payload or {});exit_date_raw=str(payload.get("exit_on_or_before_date") or "")[:10]
            try:exit_date=date.fromisoformat(exit_date_raw)
            except Exception:exit_date=None
            if exit_date is not None:
                nearest=exit_date if nearest is None or exit_date<nearest else nearest
                if today>=exit_date:due.append({"position_id":p.position_id,"symbol":p.symbol,"exit_on_or_before_date":exit_date.isoformat(),"instruction_id":guard.instruction_id,"status":guard.status})
        if due:status="CRITICAL"
        elif missing:status="DEGRADED"
        else:status="LOW"
        return {
            "status":status,"managed_option_positions":total,"expiration_guards_armed":armed,
            "missing_expiration_guards":len(missing),"due_or_overdue_expiration_guards":len(due),
            "nearest_mandatory_exit_date":nearest.isoformat() if nearest else None,
            "missing_positions":missing,"due_positions":due,
            "policy":"FULL_POSITION_EXIT_AT_LEAST_1_TRADING_DAY_BEFORE_EARLIEST_LEG_EXPIRY",
        }

    def current(self, portfolio_id="PAPER-PRIMARY"):
        with self.session_factory() as session:
            row = session.scalar(
                select(PortfolioRiskSnapshotModel)
                .where(PortfolioRiskSnapshotModel.portfolio_id == portfolio_id)
                .order_by(PortfolioRiskSnapshotModel.snapshot_timestamp.desc())
                .limit(1)
            )
            return None if row is None else self.serialize(row)

    def snapshot(self, portfolio_id="PAPER-PRIMARY", risk_snapshot_id: str | None = None):
        """Return one exact risk snapshot, or the newest observed snapshot.

        Decision-generation cycles pass ``risk_snapshot_id`` so every candidate is
        assessed against the same immutable capital state even if another process
        creates a newer raw risk observation while the cycle is running.
        """
        if risk_snapshot_id is None:
            return self.current(portfolio_id)
        with self.session_factory() as session:
            row = session.scalar(
                select(PortfolioRiskSnapshotModel).where(
                    PortfolioRiskSnapshotModel.portfolio_id == portfolio_id,
                    PortfolioRiskSnapshotModel.snapshot_id == risk_snapshot_id,
                )
            )
            return None if row is None else self.serialize(row)

    def assess(
        self,
        candidate,
        portfolio_id="PAPER-PRIMARY",
        *,
        risk_snapshot_id: str | None = None,
    ):
        """Assess a candidate against the current portfolio with explicit input integrity.

        M76.2.4 does not change portfolio thresholds. It prevents missing capital inputs
        from masquerading as an ordinary concentration/fit rejection and persists every
        governing rule with actual/threshold/pass evidence for operator diagnostics.
        """
        snapshot = self.snapshot(portfolio_id, risk_snapshot_id)
        if snapshot is None and risk_snapshot_id is not None:
            raise LookupError(
                f"Pinned portfolio risk snapshot {risk_snapshot_id} was not found "
                f"for portfolio {portfolio_id}"
            )
        snapshot = snapshot or self.build(portfolio_id)
        payload = dict(snapshot.get("payload_json") or {})
        exposures = dict(payload.get("exposures") or {})
        capital_payload = dict(payload.get("capital") or {})
        net_liquidation = number(snapshot.get("net_liquidation") or capital_payload.get("net_liquidation"))
        buying_power = number(snapshot.get("buying_power") or capital_payload.get("buying_power"))
        symbol = str(candidate.get("symbol", "UNKNOWN"))
        sector = str(candidate.get("sector", "UNKNOWN"))
        strategy = str(candidate.get("strategy", "UNKNOWN"))
        requested = number(candidate.get("capital_required") or candidate.get("maximum_loss"))
        expected_value = number(candidate.get("expected_value"))
        probability = number(candidate.get("probability"), 0.5)

        input_checks = {
            "risk_snapshot_present": bool(snapshot.get("snapshot_id")),
            "net_liquidation_positive": net_liquidation > 0,
            "buying_power_positive": buying_power > 0,
            "exposure_payload_present": isinstance(exposures, dict) and bool(exposures),
            "candidate_capital_positive": requested > 0,
        }
        input_failures = [name for name, passed in input_checks.items() if not passed]
        input_status = "READY" if not input_failures else "INPUT_INTEGRITY_BLOCK"

        symbol_exposure = number((exposures.get("symbol") or {}).get(symbol, 0))
        sector_exposure = number((exposures.get("sector") or {}).get(sector, 0))
        strategy_exposure = number((exposures.get("strategy") or {}).get(strategy, 0))

        # Never manufacture 100% concentration/heat values from a zero denominator.
        # Invalid capital context is handled explicitly as an integrity block below.
        if net_liquidation > 0:
            symbol_pct = (symbol_exposure + requested) / net_liquidation * 100
            sector_pct = (sector_exposure + requested) / net_liquidation * 100
            strategy_pct = (strategy_exposure + requested) / net_liquidation * 100
            marginal_heat = requested / net_liquidation * 100
        else:
            symbol_pct = sector_pct = strategy_pct = marginal_heat = 0.0

        current_open_risk = number(snapshot.get("open_risk") or capital_payload.get("open_risk"))
        current_heat = (current_open_risk / net_liquidation * 100) if net_liquidation > 0 else 0.0
        # Candidate risk is an incremental defined/open-risk contribution.  It is not
        # allowed to inherit or duplicate the existing portfolio's leg-level risk.
        incremental_risk = max(0.0, requested)
        marginal_heat = (incremental_risk / net_liquidation * 100) if net_liquidation > 0 else 0.0
        projected_open_risk = current_open_risk + incremental_risk
        projected_heat = (projected_open_risk / net_liquidation * 100) if net_liquidation > 0 else 0.0
        remaining_heat_capacity = max(0.0, 20.0 - projected_heat)
        penalty = (
            max(0, symbol_pct - 10) * 3
            + max(0, sector_pct - 25) * 1.5
            + max(0, strategy_pct - 35)
            + max(0, projected_heat - 20) * 3
        )
        efficiency = expected_value / requested * 100 if requested else 0
        score = clamp(65 + probability * 20 + min(15, efficiency) - penalty + (10 if symbol_exposure == 0 else 0))

        risk_budget = max(0, net_liquidation * 0.02) if net_liquidation > 0 else 0.0
        buying_power_budget = max(0, buying_power * 0.05) if buying_power > 0 else 0.0
        recommended_capital = min(requested or risk_budget, risk_budget, buying_power_budget)
        unit_risk = max(1.0, number(candidate.get("unit_risk") or requested, 1.0))
        quantity = int(recommended_capital // unit_risk) if recommended_capital else 0

        rule_evaluations = [
            {"rule_id": "M64-FIT-INPUT-001", "label": "Net liquidation available", "actual": net_liquidation, "required": "> 0", "passed": net_liquidation > 0},
            {"rule_id": "M64-FIT-INPUT-002", "label": "Buying power available", "actual": buying_power, "required": "> 0", "passed": buying_power > 0},
            {"rule_id": "M64-FIT-RISK-001", "label": "Projected symbol concentration", "actual": round(symbol_pct, 4), "required": "<= 10%", "passed": net_liquidation > 0 and symbol_pct <= 10},
            {"rule_id": "M64-FIT-RISK-002", "label": "Projected sector concentration", "actual": round(sector_pct, 4), "required": "<= 25%", "passed": net_liquidation > 0 and sector_pct <= 25},
            {"rule_id": "M64-FIT-RISK-003", "label": "Projected strategy concentration", "actual": round(strategy_pct, 4), "required": "<= 35%", "passed": net_liquidation > 0 and strategy_pct <= 35},
            {"rule_id": "M64-FIT-RISK-004A", "label": "Current portfolio heat", "actual": round(current_heat, 4), "required": "measured before candidate", "passed": net_liquidation > 0},
            {"rule_id": "M64-FIT-RISK-004B", "label": "Incremental candidate heat", "actual": round(marginal_heat, 4), "required": "candidate defined risk / NLV", "passed": net_liquidation > 0},
            {"rule_id": "M64-FIT-RISK-004", "label": "Projected portfolio heat", "actual": round(projected_heat, 4), "required": "<= 20%", "passed": net_liquidation > 0 and projected_heat <= 20},
            {"rule_id": "M64-FIT-RISK-004C", "label": "Remaining portfolio heat capacity", "actual": round(remaining_heat_capacity, 4), "required": ">= 0%", "passed": net_liquidation > 0 and projected_heat <= 20},
            {"rule_id": "M64-FIT-CAPITAL-001", "label": "At least one unit can be funded", "actual": quantity, "required": ">= 1", "passed": quantity >= 1},
        ]

        blocking_reasons: list[str] = []
        if input_status != "READY":
            blocking_reasons.append("PORTFOLIO_INPUT_INTEGRITY_BLOCK")
            blocking_reasons.extend(f"INPUT_{name.upper()}" for name in input_failures)
        if quantity <= 0:
            blocking_reasons.append("RECOMMENDED_CAPITAL_BELOW_UNIT_RISK")
        if symbol_pct > 10:
            blocking_reasons.append("SYMBOL_CONCENTRATION_LIMIT")
        if sector_pct > 25:
            blocking_reasons.append("SECTOR_CONCENTRATION_LIMIT")
        if strategy_pct > 35:
            blocking_reasons.append("STRATEGY_CONCENTRATION_LIMIT")
        if projected_heat > 20:
            blocking_reasons.append("PORTFOLIO_HEAT_LIMIT")
        blocking_reasons = list(dict.fromkeys(blocking_reasons))

        if input_status != "READY":
            score = 0.0
            recommended_capital = 0.0
            quantity = 0
            decision = "REJECT"
        else:
            decision = "ACCEPT" if score >= 70 and quantity > 0 else "REVIEW" if score >= 50 else "REJECT"

        result = {
            "assessment_status": input_status,
            "input_integrity": {
                "status": input_status,
                "checks": input_checks,
                "failures": input_failures,
                "net_liquidation": net_liquidation,
                "buying_power": buying_power,
                "risk_snapshot_id": snapshot.get("snapshot_id"),
                "risk_snapshot_status": snapshot.get("status"),
                "risk_snapshot_timestamp": snapshot.get("snapshot_timestamp"),
            },
            "portfolio_fit_score": score,
            "decision": decision,
            "recommended_quantity": quantity,
            "recommended_capital": recommended_capital,
            "marginal_risk": incremental_risk,
            "current_open_risk": current_open_risk,
            "current_portfolio_heat_pct": current_heat,
            "incremental_open_risk": incremental_risk,
            "marginal_portfolio_heat_pct": marginal_heat,
            "projected_open_risk": projected_open_risk,
            "remaining_portfolio_heat_capacity_pct": remaining_heat_capacity,
            "expected_value": expected_value,
            "projected_symbol_pct": symbol_pct,
            "projected_sector_pct": sector_pct,
            "projected_strategy_pct": strategy_pct,
            "projected_portfolio_heat_pct": projected_heat,
            "blocking_reasons": blocking_reasons,
            "reasons": self._fit_reasons(symbol_pct, sector_pct, strategy_pct, score) + [r for r in blocking_reasons if r not in self._fit_reasons(symbol_pct, sector_pct, strategy_pct, score)],
            "rule_evaluations": rule_evaluations,
            "policy_thresholds": {
                "accept_fit_score_min": 70.0,
                "review_fit_score_min": 50.0,
                "symbol_concentration_pct_max": 10.0,
                "sector_concentration_pct_max": 25.0,
                "strategy_concentration_pct_max": 35.0,
                "portfolio_heat_pct_max": 20.0,
                "risk_budget_pct": 2.0,
                "buying_power_budget_pct": 5.0,
            },
            "risk_snapshot_id": snapshot.get("snapshot_id"),
            "policy_version": self.POLICY_VERSION,
            "diagnostics_version": "M64.1-INCREMENTAL-PORTFOLIO-HEAT-1.0",
        }
        with self.session_factory() as session:
            candidate_id = str(candidate.get("candidate_id") or candidate.get("opportunity_id") or uuid4().hex)
            row = session.scalar(select(PortfolioFitAssessmentModel).where(
                PortfolioFitAssessmentModel.portfolio_id == portfolio_id,
                PortfolioFitAssessmentModel.candidate_id == candidate_id,
                PortfolioFitAssessmentModel.risk_snapshot_id == snapshot.get("snapshot_id"),
            ))
            if row is None:
                row = PortfolioFitAssessmentModel(
                    assessment_id="M64-FIT-" + uuid4().hex.upper(),
                    portfolio_id=portfolio_id, candidate_id=candidate_id,
                    risk_snapshot_id=snapshot.get("snapshot_id"), symbol=symbol,
                    portfolio_fit_score=score, recommended_quantity=quantity,
                    recommended_capital=recommended_capital, decision=decision,
                    assessed_at=now(), payload_json={**candidate, **result},
                )
                session.add(row)
            else:
                row.symbol=symbol; row.portfolio_fit_score=score
                row.recommended_quantity=quantity; row.recommended_capital=recommended_capital
                row.decision=decision; row.assessed_at=now(); row.payload_json={**candidate, **result}
            try:
                session.commit()
            except IntegrityError:
                # Another concurrent/overlapping M64 run may have materialized the
                # same governed (portfolio, candidate, risk snapshot) assessment
                # after our read and before this commit.  The database uniqueness
                # constraint is authoritative; recover by updating that row rather
                # than surfacing a duplicate-key failure to the operator.
                session.rollback()
                row = session.scalar(select(PortfolioFitAssessmentModel).where(
                    PortfolioFitAssessmentModel.portfolio_id == portfolio_id,
                    PortfolioFitAssessmentModel.candidate_id == candidate_id,
                    PortfolioFitAssessmentModel.risk_snapshot_id == snapshot.get("snapshot_id"),
                ))
                if row is None:
                    raise
                row.symbol=symbol; row.portfolio_fit_score=score
                row.recommended_quantity=quantity; row.recommended_capital=recommended_capital
                row.decision=decision; row.assessed_at=now(); row.payload_json={**candidate, **result}
                session.commit()
        return result

    def stress(self, portfolio_id="PAPER-PRIMARY"):
        snapshot = self.current(portfolio_id) or self.build(portfolio_id)
        scenarios = snapshot["payload_json"]["risk"]["stress"]
        worst = min(scenarios.items(), key=lambda item: item[1]["estimated_pnl"])
        with self.session_factory() as session:
            row = PortfolioStressSnapshotModel(
                stress_snapshot_id="M64-STRESS-" + uuid4().hex.upper(),
                portfolio_id=portfolio_id,
                risk_snapshot_id=snapshot["snapshot_id"],
                generated_at=now(),
                worst_scenario=worst[0],
                worst_loss=abs(min(0, worst[1]["estimated_pnl"])),
                payload_json=scenarios,
            )
            session.add(row)
            session.commit()
        return {
            "risk_snapshot_id": snapshot["snapshot_id"],
            "worst_scenario": worst[0],
            "worst_loss": abs(min(0, worst[1]["estimated_pnl"])),
            "scenarios": scenarios,
        }

    def _fit_reasons(self, symbol_pct, sector_pct, strategy_pct, score):
        reasons = []
        if symbol_pct > 10:
            reasons.append("SYMBOL_CONCENTRATION_LIMIT")
        if sector_pct > 25:
            reasons.append("SECTOR_CONCENTRATION_LIMIT")
        if strategy_pct > 35:
            reasons.append("STRATEGY_CONCENTRATION_LIMIT")
        if not reasons:
            reasons.append("PORTFOLIO_DIVERSIFICATION_ACCEPTABLE")
        if score >= 80:
            reasons.append("STRONG_PORTFOLIO_FIT")
        return reasons

    def serialize(self, row):
        return {column.name: getattr(row, column.name) for column in row.__table__.columns}
