from __future__ import annotations
from .paper_decision_adapter import PaperDecisionPipelineAdapter
from .paper_scan_engine import PaperScanEngine
from .paper_scan_policy import PaperScanAutomationPolicy
from .paper_scan_profile import (
    PaperScanCandidate,
    PaperScanCycleResult,
)
from .paper_signal_order_mapper import PaperSignalOrderMapper
from .paper_trading_session_service import PaperTradingSessionService

class PaperScanCycleService:
    def __init__(
        self,
        *,
        session_service: PaperTradingSessionService,
        policy: PaperScanAutomationPolicy | None = None,
    ) -> None:
        self.session_service = session_service
        self.policy = policy or PaperScanAutomationPolicy()
        self.engine = PaperScanEngine(self.policy)
        self.adapter = PaperDecisionPipelineAdapter()
        self.mapper = PaperSignalOrderMapper(self.policy)

    def run(
        self,
        *,
        session_id: str,
        candidates: tuple[PaperScanCandidate, ...],
        institutional_decisions: dict[str, object],
        risk_gateway_decisions: dict[str, object],
    ) -> PaperScanCycleResult:
        state, cycle = self.session_service.begin_cycle(session_id)
        approved_candidates, prefilter_rejected = (
            self.engine.filter_candidates(candidates)
        )

        decisions = []
        drafts = []
        rejected_count = len(prefilter_rejected)

        for candidate in approved_candidates:
            decision = self.adapter.combine(
                candidate,
                institutional_decision=institutional_decisions.get(
                    candidate.candidate_id
                ),
                risk_gateway_decision=risk_gateway_decisions.get(
                    candidate.candidate_id
                ),
                require_decision_approval=self.policy.require_decision_approval,
                require_risk_gateway_approval=self.policy.require_risk_gateway_approval,
            )
            decisions.append(decision)
            if decision.approved:
                drafts.append(
                    self.mapper.map(
                        candidate=candidate,
                        decision=decision,
                        account_id=state.session.account_id,
                    )
                )
            else:
                rejected_count += 1

        drafts = drafts[: self.policy.maximum_orders_created_per_cycle]
        self.session_service.complete_cycle(
            session_id,
            candidate_count=len(candidates),
            approved_count=sum(d.approved for d in decisions),
            submitted_count=0,
            rejected_count=rejected_count,
        )

        return PaperScanCycleResult(
            session_id=session_id,
            cycle_id=cycle.cycle_id,
            scanned_symbols=cycle.scanned_symbols,
            candidate_count=len(candidates),
            approved_count=sum(d.approved for d in decisions),
            rejected_count=rejected_count,
            order_draft_count=len(drafts),
            candidates=candidates,
            decisions=tuple(decisions),
            order_drafts=tuple(drafts),
            metadata={
                "prefilter_rejected": len(prefilter_rejected),
                "execution_deferred": True,
            },
        )
