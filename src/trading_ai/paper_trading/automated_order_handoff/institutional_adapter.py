from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .profile import AutomatedPaperOrderCandidate


def _value(source: Any, *names: str, default: Any = None) -> Any:
    if source is None:
        return default
    for name in names:
        if isinstance(source, Mapping):
            value = source.get(name)
        else:
            value = getattr(source, name, None)
        if value is not None:
            return value
    return default


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _probability(value: Any) -> float:
    number = _number(value)
    return number / 100.0 if number > 1.0 else number


def _stable_candidate_id(scan_id: str, symbol: str, strategy: str) -> str:
    digest = hashlib.sha256(
        f"{scan_id}|{symbol.upper()}|{strategy}".encode("utf-8")
    ).hexdigest()[:20]
    return f"M51-INST-{digest.upper()}"


@dataclass(frozen=True)
class InstitutionalDecisionHandoffPolicy:
    portfolio_id: str = "PAPER-PRIMARY"
    minimum_decision_confidence: float = 60.0
    minimum_probability: float = 0.50
    require_available: bool = True
    require_allowed: bool = True
    require_selected: bool = True
    accepted_actions: tuple[str, ...] = ("BUY", "SELL", "OPEN", "ENTER", "TRADE")
    accepted_readiness: tuple[str, ...] = (
        "READY",
        "APPROVED",
        "TRADE_READY",
        "EXECUTION_READY",
    )
    default_quantity: float = 1.0
    default_order_type: str = "LIMIT"
    default_time_in_force: str = "DAY"
    equity_limit_price_factor: float = 0.995

    def validate(self) -> None:
        if self.portfolio_id != "PAPER-PRIMARY":
            raise ValueError("Step 2 currently supports PAPER-PRIMARY only")
        if not 0.0 <= self.minimum_probability <= 1.0:
            raise ValueError("minimum_probability must be within [0, 1]")
        if self.default_quantity <= 0:
            raise ValueError("default_quantity must be positive")
        if not 0.0 < self.equity_limit_price_factor <= 1.0:
            raise ValueError("equity_limit_price_factor must be within (0, 1]")


@dataclass(frozen=True)
class InstitutionalDecisionHandoffConversion:
    symbol: str
    accepted: bool
    candidate: AutomatedPaperOrderCandidate | None = None
    rejection_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class InstitutionalDecisionHandoffAdapter:
    """Convert institutional scanner report rows into Step 1 candidates."""

    def __init__(
        self,
        policy: InstitutionalDecisionHandoffPolicy | None = None,
    ) -> None:
        self.policy = policy or InstitutionalDecisionHandoffPolicy()
        self.policy.validate()

    def convert_payload(
        self,
        payload: Mapping[str, Any],
    ) -> tuple[InstitutionalDecisionHandoffConversion, ...]:
        run = payload.get("run") or {}
        raw_candidates = payload.get("candidates") or ()
        decisions = run.get("decisions_by_symbol") or {}
        scan_id = str(
            run.get("scan_id")
            or (run.get("metadata") or {}).get("scan_id")
            or payload.get("scan_id")
            or "INSTITUTIONAL-SCANNER"
        )

        candidate_by_symbol: dict[str, Mapping[str, Any]] = {}
        for row in raw_candidates:
            symbol = str(_value(row, "symbol", default="")).upper()
            if symbol:
                candidate_by_symbol.setdefault(symbol, row)

        results: list[InstitutionalDecisionHandoffConversion] = []
        for symbol, decision in decisions.items():
            normalized_symbol = str(symbol).upper()
            market_candidate = candidate_by_symbol.get(normalized_symbol)
            results.append(
                self.convert_one(
                    scan_id=scan_id,
                    symbol=normalized_symbol,
                    decision=decision,
                    market_candidate=market_candidate,
                )
            )
        return tuple(results)

    def convert_one(
        self,
        *,
        scan_id: str,
        symbol: str,
        decision: Mapping[str, Any],
        market_candidate: Mapping[str, Any] | None,
    ) -> InstitutionalDecisionHandoffConversion:
        rejections: list[str] = []
        warnings: list[str] = []

        available = bool(_value(decision, "available", default=False))
        allowed = bool(_value(decision, "allowed", default=False))
        selected = bool(_value(decision, "selected", default=False))
        action = str(_value(decision, "action", default="HOLD")).upper()
        readiness = str(_value(decision, "readiness", default="UNKNOWN")).upper()
        strategy = str(_value(decision, "strategy", default="UNAVAILABLE"))
        confidence = _number(
            _value(decision, "decision_confidence", "ranking_score", default=0.0)
        )
        probability = _probability(
            _value(
                decision,
                "calibrated_probability",
                "probability_of_profit",
                "probability",
                default=0.0,
            )
        )

        if self.policy.require_available and not available:
            rejections.append("INSTITUTIONAL_DECISION_UNAVAILABLE")
        if self.policy.require_allowed and not allowed:
            rejections.append("INSTITUTIONAL_DECISION_NOT_ALLOWED")
        if self.policy.require_selected and not selected:
            rejections.append("INSTITUTIONAL_DECISION_NOT_SELECTED")
        if action not in self.policy.accepted_actions:
            rejections.append("INSTITUTIONAL_ACTION_NOT_EXECUTABLE")
        if readiness not in self.policy.accepted_readiness:
            rejections.append("INSTITUTIONAL_READINESS_NOT_APPROVED")
        if confidence < self.policy.minimum_decision_confidence:
            rejections.append("INSTITUTIONAL_CONFIDENCE_BELOW_MINIMUM")
        if probability < self.policy.minimum_probability:
            rejections.append("INSTITUTIONAL_PROBABILITY_BELOW_MINIMUM")
        if market_candidate is None:
            rejections.append("MARKET_CANDIDATE_NOT_FOUND")

        if rejections:
            return InstitutionalDecisionHandoffConversion(
                symbol=symbol,
                accepted=False,
                rejection_reasons=tuple(dict.fromkeys(rejections)),
                warnings=tuple(warnings),
                metadata={
                    "scan_id": scan_id,
                    "action": action,
                    "readiness": readiness,
                    "decision_confidence": confidence,
                    "probability": probability,
                },
            )

        source = _value(market_candidate, "source", default=market_candidate) or {}
        metadata = dict(_value(source, "metadata", default={}) or {})
        metadata.update(dict(_value(market_candidate, "metadata", default={}) or {}))

        side = self._side(action, metadata)
        asset_class = str(
            metadata.get("asset_class")
            or metadata.get("security_type")
            or "EQUITY"
        ).upper()
        if asset_class in {"STK", "STOCK"}:
            asset_class = "EQUITY"
        if asset_class in {"OPT", "OPTIONS"}:
            asset_class = "OPTION"

        price = _number(
            _value(
                market_candidate,
                "price",
                default=_value(source, "price", default=metadata.get("underlying_price")),
            )
        )
        limit_price = _number(
            metadata.get("limit_price")
            or metadata.get("option_price")
            or metadata.get("recommended_entry_price"),
            default=0.0,
        )
        if limit_price <= 0 and asset_class == "EQUITY" and price > 0:
            limit_price = round(price * self.policy.equity_limit_price_factor, 2)
        if limit_price <= 0:
            rejections.append("EXECUTABLE_LIMIT_PRICE_NOT_AVAILABLE")

        quantity = _number(
            metadata.get("contracts")
            or metadata.get("quantity")
            or metadata.get("recommended_quantity"),
            default=self.policy.default_quantity,
        )
        if quantity <= 0:
            rejections.append("EXECUTABLE_QUANTITY_NOT_AVAILABLE")

        expiry = str(metadata.get("expiry") or metadata.get("expiration") or "")
        strike = metadata.get("strike")
        right = str(
            metadata.get("right")
            or metadata.get("option_type")
            or metadata.get("contract_type")
            or ""
        ).upper()
        local_symbol = str(
            metadata.get("option_symbol")
            or metadata.get("local_symbol")
            or metadata.get("contract_symbol")
            or ""
        )
        contract_id = int(_number(metadata.get("contract_id") or metadata.get("conid"), 0))
        primary_exchange = str(
            metadata.get("primary_exchange")
            or metadata.get("listing_exchange")
            or ""
        )

        if asset_class == "OPTION":
            if not expiry:
                rejections.append("OPTION_EXPIRY_NOT_AVAILABLE")
            if _number(strike, 0.0) <= 0:
                rejections.append("OPTION_STRIKE_NOT_AVAILABLE")
            if right not in {"C", "P", "CALL", "PUT"}:
                rejections.append("OPTION_RIGHT_NOT_AVAILABLE")
            if not local_symbol and contract_id <= 0:
                warnings.append("OPTION_CONTRACT_IDENTIFIER_NOT_AVAILABLE")

        if rejections:
            return InstitutionalDecisionHandoffConversion(
                symbol=symbol,
                accepted=False,
                rejection_reasons=tuple(dict.fromkeys(rejections)),
                warnings=tuple(dict.fromkeys(warnings)),
                metadata={
                    "scan_id": scan_id,
                    "asset_class": asset_class,
                    "decision_confidence": confidence,
                    "probability": probability,
                },
            )

        candidate = AutomatedPaperOrderCandidate(
            candidate_id=_stable_candidate_id(scan_id, symbol, strategy),
            portfolio_id=self.policy.portfolio_id,
            symbol=symbol,
            asset_class=asset_class,
            side=side,
            quantity=quantity,
            order_type=self.policy.default_order_type,
            time_in_force=self.policy.default_time_in_force,
            limit_price=limit_price,
            primary_exchange=primary_exchange,
            currency=str(metadata.get("currency") or "USD"),
            expiry=expiry,
            strike=None if strike is None else _number(strike),
            right=right,
            multiplier=str(metadata.get("multiplier") or ("100" if asset_class == "OPTION" else "")),
            local_symbol=local_symbol,
            contract_id=contract_id,
            institutional_allowed=True,
            risk_gateway_allowed=bool(
                metadata.get("risk_gateway_allowed", allowed)
            ),
            decision_score=confidence,
            probability=probability,
            strategy_name=strategy,
            metadata={
                **metadata,
                "source": "INSTITUTIONAL_SCANNER_REPORT",
                "scan_id": scan_id,
                "institutional_action": action,
                "institutional_readiness": readiness,
                "institutional_expected_return": _number(
                    _value(decision, "expected_return", default=0.0)
                ),
                "institutional_reward_risk_ratio": _number(
                    _value(decision, "reward_risk_ratio", default=0.0)
                ),
            },
        )
        return InstitutionalDecisionHandoffConversion(
            symbol=symbol,
            accepted=True,
            candidate=candidate,
            warnings=tuple(dict.fromkeys(warnings)),
            metadata={
                "scan_id": scan_id,
                "decision_confidence": confidence,
                "probability": probability,
                "asset_class": asset_class,
            },
        )

    @staticmethod
    def _side(action: str, metadata: Mapping[str, Any]) -> str:
        explicit = str(metadata.get("side") or metadata.get("direction") or "").upper()
        if explicit in {"BUY", "SELL"}:
            return explicit
        signal = str(metadata.get("signal") or "").upper()
        if "PUT" in signal or signal in {"BEARISH", "SHORT", "SELL"}:
            return "BUY"
        if action == "SELL":
            return "SELL"
        return "BUY"
