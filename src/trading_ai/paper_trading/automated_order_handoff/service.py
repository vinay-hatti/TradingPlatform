from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from sqlalchemy import select

from trading_ai.authoritative_paper_trading.database_models import CanonicalOrderModel
from trading_ai.authoritative_paper_trading.repositories import DatabaseOrderRepository
from trading_ai.broker.ibkr.database_models import BrokerAccountBindingModel
from trading_ai.broker.ibkr.order_service import IbkrPaperOrderGovernanceService
from trading_ai.order_management.order_service import CanonicalOrderService

from .engine import AutomatedPaperOrderHandoffEngine
from .factory import AutomatedPaperOrderFactory
from .policy import AutomatedPaperOrderHandoffPolicy
from .profile import (
    AutomatedPaperOrderCandidate,
    AutomatedPaperOrderHandoffResult,
)


class AutomatedPaperOrderHandoffService:
    """Governed candidate-to-IBKR paper-order handoff.

    DRY_RUN is the default and never calls the broker transport. SUBMIT requires
    an enabled Milestone 50 routing control and an exact per-account confirmation.
    """

    def __init__(
        self,
        session_factory: Callable,
        *,
        policy: AutomatedPaperOrderHandoffPolicy | None = None,
        broker_order_service=None,
    ) -> None:
        self.session_factory = session_factory
        self.policy = policy or AutomatedPaperOrderHandoffPolicy()
        self.policy.validate()
        self.engine = AutomatedPaperOrderHandoffEngine(self.policy)
        self.factory = AutomatedPaperOrderFactory()
        self.canonical_service = CanonicalOrderService()
        self.governance = IbkrPaperOrderGovernanceService(session_factory)
        self.broker_order_service = broker_order_service

    def execute(
        self,
        candidate: AutomatedPaperOrderCandidate,
        *,
        mode: str = "DRY_RUN",
        confirmation: str = "",
    ) -> AutomatedPaperOrderHandoffResult:
        normalized_mode = mode.upper()
        if normalized_mode not in {"DRY_RUN", "SUBMIT"}:
            raise ValueError("mode must be DRY_RUN or SUBMIT")

        assessment = self.engine.assess(candidate)
        aggregate_id, client_order_id, idempotency_key = self.factory.identifiers(candidate)
        if not assessment.allowed:
            return AutomatedPaperOrderHandoffResult(
                milestone=51,
                phase="AUTOMATED_PAPER_ORDER_HANDOFF",
                step=1,
                mode=normalized_mode,
                portfolio_id=candidate.portfolio_id,
                candidate_id=candidate.candidate_id,
                aggregate_id=aggregate_id,
                client_order_id=client_order_id,
                idempotency_key=idempotency_key,
                canonical_order_created=False,
                replayed=False,
                assessment=assessment,
                status="REJECTED_BY_HANDOFF_POLICY",
            )

        binding = self._binding(candidate.portfolio_id)
        command = self.factory.canonical_command(candidate)
        aggregate, created, replayed = self._ensure_canonical(command)
        ibkr_request = self.factory.ibkr_request(
            candidate, broker_account_id=binding.broker_account_id
        )

        broker_submission = None
        status = "DRY_RUN_READY"
        if normalized_mode == "SUBMIT":
            expected = f"SUBMIT AUTOMATED IBKR PAPER ORDER {candidate.portfolio_id}"
            if confirmation != expected:
                raise PermissionError(
                    "submission confirmation mismatch; expected exactly: " + expected
                )
            control = self.governance.status(candidate.portfolio_id)
            if control["environment"] != "PAPER" or control["live_trading_enabled"]:
                raise PermissionError("paper-only routing governance failed")
            if not control["paper_order_submission_enabled"]:
                raise PermissionError("IBKR paper order routing is disabled")
            if self.broker_order_service is None:
                raise RuntimeError("broker_order_service is required for SUBMIT mode")
            broker_submission = self.broker_order_service.submit(ibkr_request)
            status = (
                "BROKER_ORDER_REPLAYED"
                if broker_submission.get("replayed")
                else "BROKER_ORDER_SUBMITTED"
            )

        return AutomatedPaperOrderHandoffResult(
            milestone=51,
            phase="AUTOMATED_PAPER_ORDER_HANDOFF",
            step=1,
            mode=normalized_mode,
            portfolio_id=candidate.portfolio_id,
            candidate_id=candidate.candidate_id,
            aggregate_id=aggregate_id,
            client_order_id=client_order_id,
            idempotency_key=idempotency_key,
            canonical_order_created=created,
            replayed=replayed,
            assessment=assessment,
            canonical_order=aggregate.to_dict(),
            ibkr_request=asdict(ibkr_request),
            broker_submission=broker_submission,
            status=status,
            warnings=assessment.warnings,
            metadata={
                "environment": "PAPER",
                "live_trading_enabled": False,
                "broker_account_masked": (
                    binding.broker_account_id[:2]
                    + "*" * max(0, len(binding.broker_account_id) - 4)
                    + binding.broker_account_id[-2:]
                ),
            },
        )

    def _binding(self, portfolio_id: str) -> BrokerAccountBindingModel:
        session = self.session_factory()
        try:
            binding = session.scalar(
                select(BrokerAccountBindingModel).where(
                    BrokerAccountBindingModel.portfolio_id == portfolio_id,
                    BrokerAccountBindingModel.broker_name == "INTERACTIVE_BROKERS",
                )
            )
            if binding is None:
                raise KeyError(f"IBKR binding not found for {portfolio_id}")
            if binding.broker_environment != "PAPER":
                raise PermissionError("only PAPER broker bindings are accepted")
            if binding.live_trading_enabled:
                raise PermissionError("live trading must remain disabled")
            session.expunge(binding)
            return binding
        finally:
            session.close()

    def _ensure_canonical(self, command):
        session = self.session_factory()
        try:
            existing = session.scalar(
                select(CanonicalOrderModel).where(
                    CanonicalOrderModel.idempotency_key == command.idempotency_key
                )
            )
            repository = DatabaseOrderRepository(session)
            if existing is not None:
                aggregate = repository.require(existing.aggregate_id)
                return aggregate, False, True

            transition = self.canonical_service.create(command)
            if not transition.allowed or transition.aggregate is None:
                raise ValueError(
                    "canonical order rejected: "
                    + ",".join(transition.rejection_reasons)
                )
            # The idempotency SELECT above autobegins the SQLAlchemy
            # transaction. DatabaseOrderRepository is explicitly designed to
            # use the caller's active transaction, so starting another
            # session.begin() here raises InvalidRequestError.
            repository.create(transition.aggregate)
            if transition.event is not None:
                repository.append_event(transition.event)
            session.commit()
            return transition.aggregate, True, False
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
