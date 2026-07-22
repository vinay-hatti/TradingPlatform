from __future__ import annotations

from collections import Counter

from .construction_profile import NormalizedPortfolioCandidate, PortfolioConstructionPolicyProfile


class PortfolioConstructionGovernancePolicy:
    def __init__(self, profile: PortfolioConstructionPolicyProfile | None = None):
        self.profile = profile or PortfolioConstructionPolicyProfile()

    def candidate_rejections(self, candidate: NormalizedPortfolioCandidate, existing_positions: list[dict]) -> list[str]:
        reasons: list[str] = []
        p = self.profile
        if p.require_allowed and not candidate.allowed:
            reasons.append("CANDIDATE_NOT_ALLOWED")
        if p.require_selected and not candidate.selected:
            reasons.append("CANDIDATE_NOT_SELECTED")
        if candidate.ranking_score < p.minimum_ranking_score:
            reasons.append("RANKING_SCORE_BELOW_MINIMUM")
        if candidate.strategy_score < p.minimum_strategy_score:
            reasons.append("STRATEGY_SCORE_BELOW_MINIMUM")
        if candidate.portfolio_fit_score < p.minimum_portfolio_fit_score:
            reasons.append("PORTFOLIO_FIT_SCORE_BELOW_MINIMUM")
        if candidate.risk_profile == "UNDEFINED_RISK" and not p.allow_undefined_risk:
            reasons.append("UNDEFINED_RISK_NOT_ALLOWED")
        if candidate.readiness == "RESEARCH_ONLY" and not p.allow_research_positions:
            reasons.append("RESEARCH_POSITION_NOT_ALLOWED")
        if p.allowed_readiness and candidate.readiness not in p.allowed_readiness and not (
            p.allow_research_positions and candidate.readiness == "RESEARCH_ONLY"
        ):
            reasons.append("READINESS_NOT_ELIGIBLE")

        open_positions = [x for x in existing_positions if str(x.get("status", "OPEN")).upper() == "OPEN"]
        counts = {
            "symbol": Counter(str(x.get("symbol", "")).upper() for x in open_positions),
            "sector": Counter(str(x.get("sector", "UNKNOWN")).upper() for x in open_positions),
            "strategy": Counter(str(x.get("strategy_type", x.get("strategy", ""))).upper() for x in open_positions),
            "direction": Counter(str(x.get("direction", "")).upper() for x in open_positions),
            "correlation": Counter(str(x.get("correlation_group", "")).upper() for x in open_positions if x.get("correlation_group")),
        }
        checks = (
            (counts["symbol"][candidate.symbol], p.maximum_positions_per_symbol, "SYMBOL_POSITION_LIMIT_REACHED"),
            (counts["sector"][candidate.sector], p.maximum_positions_per_sector, "SECTOR_POSITION_LIMIT_REACHED"),
            (counts["strategy"][candidate.strategy], p.maximum_positions_per_strategy, "STRATEGY_POSITION_LIMIT_REACHED"),
            (counts["direction"][candidate.direction], p.maximum_positions_per_direction, "DIRECTION_POSITION_LIMIT_REACHED"),
        )
        for current, maximum, code in checks:
            if current >= maximum:
                reasons.append(code)
        if candidate.correlation_group and counts["correlation"][candidate.correlation_group] >= p.maximum_positions_per_correlation_group:
            reasons.append("CORRELATION_GROUP_POSITION_LIMIT_REACHED")
        return sorted(set(reasons))
