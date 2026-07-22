from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trading_ai.strategy_engine.institutional_opportunity import InstitutionalOpportunity
from trading_ai.strategy_engine.institutional_ranked_opportunity import InstitutionalRankedOpportunity
from trading_ai.strategy_engine.portfolio_risk_limits import PortfolioRiskLimits
from trading_ai.strategy_engine.portfolio_service import PortfolioService

from .construction_policy import PortfolioConstructionGovernancePolicy
from .construction_profile import NormalizedPortfolioCandidate, PortfolioConstructionPolicyProfile, PortfolioConstructionRun
from .serialization import read_json, write_json_atomic


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(value if value is not None else default)
    except (TypeError, ValueError):
        return default


class PortfolioCandidateNormalizer:
    def normalize(self, payload: dict[str, Any], index: int = 0) -> NormalizedPortfolioCandidate:
        ranked = payload.get("ranked_opportunity", payload)
        opportunity = ranked.get("opportunity", payload.get("opportunity", ranked))
        if not isinstance(opportunity, dict):
            raise ValueError("Candidate opportunity must be a JSON object")
        symbol = str(opportunity.get("symbol", ranked.get("symbol", ""))).upper().strip()
        strategy = str(opportunity.get("strategy", opportunity.get("strategy_type", ranked.get("strategy", "")))).upper().strip()
        if not symbol or not strategy:
            raise ValueError("Candidate requires symbol and strategy")
        direction = str(opportunity.get("direction", ranked.get("direction", "NEUTRAL"))).upper()
        ranking_score = _f(ranked.get("ranking_score", payload.get("ranking_score", opportunity.get("ranking_score", 0.0))))
        raw_score = _f(ranked.get("raw_ranking_score", ranking_score))
        greeks = opportunity.get("greeks", {}) or {}
        metadata = dict(opportunity.get("metadata", {}) or {})
        candidate_id = str(payload.get("candidate_id", metadata.get("candidate_id", ""))).strip()
        if not candidate_id:
            digest = hashlib.sha256(f"{symbol}|{strategy}|{opportunity.get('expiry','')}|{opportunity.get('strike','')}|{index}".encode()).hexdigest()[:16]
            candidate_id = f"CANDIDATE-{digest.upper()}"
        return NormalizedPortfolioCandidate(
            candidate_id=candidate_id, symbol=symbol, strategy=strategy, direction=direction,
            ranking_score=ranking_score, raw_ranking_score=raw_score,
            strategy_score=_f(opportunity.get("strategy_score", ranked.get("strategy_score", 0.0))),
            portfolio_fit_score=_f(opportunity.get("portfolio_fit_score", ranked.get("portfolio_fit_score", 50.0)), 50.0),
            expected_return_pct=_f(opportunity.get("expected_return_pct")), expected_profit=_f(opportunity.get("expected_profit")),
            maximum_loss=_f(opportunity.get("maximum_loss")), capital_required=_f(opportunity.get("capital_required")),
            allowed=bool(ranked.get("allowed", opportunity.get("allowed", True))), selected=bool(ranked.get("selected", True)),
            readiness=str(opportunity.get("readiness", ranked.get("readiness", "RESEARCH_ONLY"))).upper(),
            action=str(ranked.get("action", opportunity.get("recommendation", "WATCHLIST"))).upper(),
            recommendation=str(opportunity.get("recommendation", ranked.get("action", "WATCHLIST"))).upper(),
            market_regime=str(opportunity.get("market_regime", "UNKNOWN")).upper(),
            probability_of_profit=opportunity.get("probability_of_profit"), sector=str(opportunity.get("sector", "UNKNOWN")).upper(),
            industry=str(opportunity.get("industry", "UNKNOWN")).upper(), correlation_group=str(opportunity.get("correlation_group", "")).upper(),
            expiry=str(opportunity.get("expiry", "")), dte=_i(opportunity.get("dte")), strike=opportunity.get("strike"),
            long_strike=opportunity.get("long_strike"), short_strike=opportunity.get("short_strike"), option_symbol=str(opportunity.get("option_symbol", "")),
            premium_type=str(opportunity.get("premium_type", "")).upper(), risk_profile=str(opportunity.get("risk_profile", "DEFINED_RISK")).upper(),
            complexity=str(opportunity.get("complexity", "STANDARD")).upper(), greeks={k: _f(v) for k, v in greeks.items()},
            warnings=tuple(ranked.get("warnings", opportunity.get("warnings", [])) or []),
            rejection_reasons=tuple(ranked.get("rejection_reasons", opportunity.get("rejection_reasons", [])) or []), metadata=metadata,
        )

    def load_file(self, path: Path) -> list[NormalizedPortfolioCandidate]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            rows = payload.get("ranked_opportunities", payload.get("candidates", payload.get("opportunities", [payload])))
        else:
            rows = payload
        if not isinstance(rows, list):
            raise ValueError("Candidate file must contain a list or a supported list field")
        return [self.normalize(row, index) for index, row in enumerate(rows) if isinstance(row, dict)]


class PortfolioConstructionOrchestrationService:
    def __init__(self, profile: PortfolioConstructionPolicyProfile | None = None):
        self.profile = profile or PortfolioConstructionPolicyProfile()
        self.governance = PortfolioConstructionGovernancePolicy(self.profile)
        self.normalizer = PortfolioCandidateNormalizer()

    def construct(self, candidates: list[NormalizedPortfolioCandidate], registry_file: Path, output_file: Path | None = None, source_file: str = "") -> PortfolioConstructionRun:
        registry = read_json(registry_file)
        account = registry.get("account", {})
        existing_positions = list(registry.get("positions", []))
        open_positions = [x for x in existing_positions if str(x.get("status", "OPEN")).upper() == "OPEN"]
        nlv = _f(registry.get("net_liquidation_value", account.get("initial_capital", 100000.0)), 100000.0)
        cash = _f(registry.get("cash_balance", nlv), nlv)
        committed = sum(_f(x.get("capital_committed")) for x in open_positions)
        existing_risk = sum(_f(x.get("maximum_loss")) for x in open_positions)

        eligible: list[NormalizedPortfolioCandidate] = []
        rejected: list[dict[str, Any]] = []
        for candidate in candidates:
            reasons = self.governance.candidate_rejections(candidate, open_positions)
            reasons.extend(candidate.rejection_reasons)
            if reasons:
                rejected.append({"candidate_id": candidate.candidate_id, "symbol": candidate.symbol, "strategy": candidate.strategy, "ranking_score": candidate.ranking_score, "reasons": sorted(set(reasons)), "warnings": list(candidate.warnings)})
            else:
                eligible.append(candidate)

        available_exposure = max(nlv * self.profile.maximum_portfolio_exposure_pct - committed, 0.0)
        available_risk = max(nlv * self.profile.maximum_total_risk_pct - existing_risk, 0.0)
        available_cash = max(cash - nlv * self.profile.reserve_cash_pct, 0.0)
        available_capital = min(available_exposure, available_cash)
        remaining_slots = max(min(self.profile.maximum_new_positions, self.profile.maximum_new_positions - 0), 0)

        exposure_pct = min(available_capital / nlv, self.profile.maximum_portfolio_exposure_pct) if nlv > 0 else 0.0
        risk_pct = min(available_risk / nlv, self.profile.maximum_total_risk_pct) if nlv > 0 else 0.0
        limits = PortfolioRiskLimits(
            initial_capital=nlv, maximum_portfolio_exposure_pct=exposure_pct, maximum_total_risk_pct=risk_pct,
            maximum_position_pct=self.profile.maximum_position_pct, maximum_risk_per_trade_pct=self.profile.maximum_risk_per_trade_pct,
            minimum_position_dollars=self.profile.minimum_position_dollars, maximum_contracts_per_position=self.profile.maximum_contracts_per_position,
            reserve_cash_pct=0.0, maximum_positions=max(remaining_slots, 1),
            maximum_positions_per_symbol=self.profile.maximum_positions_per_symbol, maximum_positions_per_sector=self.profile.maximum_positions_per_sector,
            maximum_positions_per_strategy=self.profile.maximum_positions_per_strategy, maximum_positions_per_direction=self.profile.maximum_positions_per_direction,
            maximum_positions_per_correlation_group=self.profile.maximum_positions_per_correlation_group,
            maximum_symbol_exposure_pct=self.profile.maximum_symbol_exposure_pct, maximum_sector_exposure_pct=self.profile.maximum_sector_exposure_pct,
            maximum_strategy_exposure_pct=self.profile.maximum_strategy_exposure_pct, maximum_direction_exposure_pct=self.profile.maximum_direction_exposure_pct,
            maximum_correlation_group_exposure_pct=self.profile.maximum_correlation_group_exposure_pct,
            maximum_absolute_delta=max(self.profile.maximum_absolute_delta - abs(sum(_f(x.get("delta")) for x in open_positions)), 0.0),
            maximum_absolute_gamma=max(self.profile.maximum_absolute_gamma - abs(sum(_f(x.get("gamma")) for x in open_positions)), 0.0),
            maximum_absolute_theta=max(self.profile.maximum_absolute_theta - abs(sum(_f(x.get("theta")) for x in open_positions)), 0.0),
            maximum_absolute_vega=max(self.profile.maximum_absolute_vega - abs(sum(_f(x.get("vega")) for x in open_positions)), 0.0),
            maximum_absolute_rho=max(self.profile.maximum_absolute_rho - abs(sum(_f(x.get("rho")) for x in open_positions)), 0.0),
            minimum_net_delta=self.profile.minimum_net_delta, maximum_net_delta=self.profile.maximum_net_delta,
            minimum_ranking_score=self.profile.minimum_ranking_score, minimum_strategy_score=self.profile.minimum_strategy_score,
            minimum_portfolio_fit_score=self.profile.minimum_portfolio_fit_score, allow_research_positions=self.profile.allow_research_positions,
            allow_undefined_risk=self.profile.allow_undefined_risk, use_risk_based_sizing=self.profile.use_risk_based_sizing, use_score_scaling=self.profile.use_score_scaling,
        )
        ranked_objects = [self._to_ranked(c, idx + 1) for idx, c in enumerate(eligible)]
        if ranked_objects and available_capital >= self.profile.minimum_position_dollars and remaining_slots > 0:
            result = PortfolioService(limits).construct(ranked_objects)
            positions = [self._position_dict(x) for x in result.positions]
            rejected.extend(asdict(x) for x in result.rejected)
            warnings = list(result.warnings)
            recommendations = list(result.recommendations)
            scores = (result.portfolio_score, result.diversification_score, result.risk_score, result.capital_efficiency_score)
            readiness = result.readiness
            valid = result.valid
        else:
            positions, warnings, recommendations = [], ["NO_AVAILABLE_PORTFOLIO_CAPACITY"], ["Release capital or revise portfolio constraints before construction."]
            scores, readiness, valid = (0.0, 0.0, 0.0, 0.0), "NOT_READY", False
        proposed_capital = sum(_f(x.get("capital_required")) for x in positions)
        stamp = _now()
        digest = hashlib.sha256(f"{self.profile.portfolio_id}|{stamp}|{len(candidates)}".encode()).hexdigest()[:16].upper()
        run = PortfolioConstructionRun(
            run_id=f"M36-P2-CONSTRUCTION-{digest}", portfolio_id=self.profile.portfolio_id,
            status="COMPLETE" if valid else "REVIEW_REQUIRED", readiness=readiness,
            candidate_count=len(candidates), eligible_candidate_count=len(eligible), proposed_position_count=len(positions),
            rejected_candidate_count=len(rejected), existing_position_count=len(open_positions), net_liquidation_value=round(nlv, 2),
            cash_balance=round(cash, 2), existing_capital_committed=round(committed, 2), available_capital=round(available_capital, 2),
            proposed_capital=round(proposed_capital, 2), combined_capital=round(committed + proposed_capital, 2),
            portfolio_score=scores[0], diversification_score=scores[1], risk_score=scores[2], capital_efficiency_score=scores[3],
            proposed_positions=tuple(positions), rejections=tuple(rejected), warnings=tuple(warnings), recommendations=tuple(recommendations),
            policy=self.profile.to_dict(), generated_at=stamp, source_file=source_file,
        )
        if output_file:
            write_json_atomic(output_file, run.to_dict())
        return run

    def construct_file(self, candidate_file: Path, registry_file: Path, output_file: Path) -> PortfolioConstructionRun:
        return self.construct(self.normalizer.load_file(candidate_file), registry_file, output_file, str(candidate_file))

    def _to_ranked(self, c: NormalizedPortfolioCandidate, rank: int) -> InstitutionalRankedOpportunity:
        g = c.greeks
        opportunity = InstitutionalOpportunity(
            symbol=c.symbol, strategy=c.strategy, direction=c.direction, market_regime=c.market_regime,
            strategy_score=c.strategy_score, allowed=c.allowed, readiness={"READY": "RESEARCH_READY", "EXECUTION_READY": "PAPER_TRADING", "APPROVED": "PAPER_TRADING"}.get(c.readiness, c.readiness), recommendation=c.recommendation,
            expected_return_pct=c.expected_return_pct, expected_profit=c.expected_profit, maximum_loss=c.maximum_loss,
            capital_required=c.capital_required, probability_of_profit=c.probability_of_profit, portfolio_fit_score=c.portfolio_fit_score,
            strike=c.strike, long_strike=c.long_strike, short_strike=c.short_strike, expiry=c.expiry, dte=c.dte,
            premium_type=c.premium_type, risk_profile=c.risk_profile, complexity=c.complexity, sector=c.sector, industry=c.industry,
            correlation_group=c.correlation_group, option_symbol=c.option_symbol, warnings=list(c.warnings), metadata={**c.metadata, "greeks": g},
        )
        opportunity.greeks_profile = type("Greeks", (), {
            "net_delta": _f(g.get("net_delta", g.get("delta", 0.0))),
            "net_gamma": _f(g.get("net_gamma", g.get("gamma", 0.0))),
            "net_theta": _f(g.get("net_theta", g.get("theta", 0.0))),
            "net_vega": _f(g.get("net_vega", g.get("vega", 0.0))),
            "net_rho": _f(g.get("net_rho", g.get("rho", 0.0))),
        })()
        return InstitutionalRankedOpportunity(rank=rank, opportunity=opportunity, ranking_score=c.ranking_score, raw_ranking_score=c.raw_ranking_score,
            grade="", tier="", action=c.action, selected=(c.selected or not self.profile.require_selected), allowed=c.allowed, primary_reason="", diversification_reason="", warnings=list(c.warnings))

    @staticmethod
    def _position_dict(position: Any) -> dict[str, Any]:
        fields = (
            "symbol", "strategy", "direction", "contracts", "capital_required",
            "maximum_loss", "expected_profit", "expected_return_pct", "allocation_pct",
            "risk_pct", "delta", "gamma", "theta", "vega", "rho", "sector",
            "industry", "correlation_group", "ranking_score", "strategy_score",
            "portfolio_fit_score", "readiness", "action", "expiry", "dte", "strike",
            "long_strike", "short_strike", "option_symbol", "premium_type",
            "risk_profile", "complexity", "warnings", "metadata",
        )
        payload = {name: getattr(position, name) for name in fields}
        payload["candidate_id"] = getattr(getattr(position, "source_opportunity", None), "metadata", {}).get("candidate_id", "")
        return payload
