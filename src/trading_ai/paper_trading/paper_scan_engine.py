from __future__ import annotations
from .paper_scan_policy import PaperScanAutomationPolicy
from .paper_scan_profile import PaperScanCandidate

class PaperScanEngine:
    def __init__(self, policy: PaperScanAutomationPolicy | None = None) -> None:
        self.policy = policy or PaperScanAutomationPolicy()
        self.policy.validate()

    def filter_candidates(
        self,
        candidates: tuple[PaperScanCandidate, ...],
    ) -> tuple[tuple[PaperScanCandidate, ...], tuple[PaperScanCandidate, ...]]:
        if len(candidates) > self.policy.maximum_candidates_per_cycle:
            candidates = candidates[: self.policy.maximum_candidates_per_cycle]

        approved = []
        rejected = []
        seen = set()

        for candidate in candidates:
            valid = True
            key = (candidate.symbol.upper(), candidate.strategy_name.upper())
            if (
                self.policy.reject_duplicate_symbol_strategy
                and key in seen
            ):
                valid = False
            seen.add(key)

            if candidate.score < self.policy.minimum_candidate_score:
                valid = False
            if candidate.probability < self.policy.minimum_decision_probability:
                valid = False
            if (
                self.policy.reject_missing_market_price
                and (candidate.market_price is None or candidate.market_price <= 0)
            ):
                valid = False
            if candidate.asset_class.upper() == "OPTION":
                if (
                    self.policy.reject_missing_expiration_for_options
                    and not candidate.expiration
                ):
                    valid = False
                if (
                    self.policy.reject_missing_strike_for_options
                    and candidate.strike is None
                ):
                    valid = False

            (approved if valid else rejected).append(candidate)

        return (
            tuple(approved[: self.policy.maximum_approved_candidates_per_cycle]),
            tuple(rejected),
        )
