from __future__ import annotations

from typing import Callable

from sqlalchemy import select

from trading_ai.authoritative_paper_trading.database_models import CanonicalOrderModel
from trading_ai.broker.ibkr.database_models import (
    BrokerExecutionModel,
    BrokerOrderModel,
)

from .profile import BrokerExecutionSnapshot, BrokerOrderLifecycleSnapshot


class AutomatedLifecycleRepository:
    def __init__(self, session_factory: Callable) -> None:
        self.session_factory = session_factory

    def orders(self, portfolio_id: str) -> tuple[BrokerOrderLifecycleSnapshot, ...]:
        session = self.session_factory()
        try:
            rows = list(
                session.scalars(
                    select(BrokerOrderModel)
                    .where(BrokerOrderModel.portfolio_id == portfolio_id)
                    .order_by(BrokerOrderModel.updated_at.desc())
                ).all()
            )
            output: list[BrokerOrderLifecycleSnapshot] = []
            for row in rows:
                canonical = session.get(CanonicalOrderModel, row.aggregate_id)
                output.append(
                    BrokerOrderLifecycleSnapshot(
                        aggregate_id=row.aggregate_id,
                        broker_order_id=int(row.broker_order_id),
                        symbol=row.symbol,
                        security_type=row.security_type,
                        side=row.side,
                        quantity=float(row.quantity),
                        status=row.status,
                        filled_quantity=float(row.filled_quantity or 0.0),
                        remaining_quantity=float(row.remaining_quantity or 0.0),
                        average_fill_price=float(row.average_fill_price or 0.0),
                        submitted_at=row.submitted_at,
                        updated_at=row.updated_at,
                        canonical_state="" if canonical is None else canonical.state,
                        canonical_terminal_at=(
                            "" if canonical is None else (canonical.terminal_at or "")
                        ),
                        metadata={
                            "broker_order_record_id": row.broker_order_record_id,
                            "permanent_id": int(row.permanent_id or 0),
                            "client_order_id": row.client_order_id,
                        },
                    )
                )
            return tuple(output)
        finally:
            session.close()

    def executions(self, portfolio_id: str) -> tuple[BrokerExecutionSnapshot, ...]:
        session = self.session_factory()
        try:
            rows = list(
                session.scalars(
                    select(BrokerExecutionModel)
                    .where(BrokerExecutionModel.portfolio_id == portfolio_id)
                    .order_by(
                        BrokerExecutionModel.executed_at,
                        BrokerExecutionModel.execution_id,
                    )
                ).all()
            )
            return tuple(
                BrokerExecutionSnapshot(
                    execution_id=row.execution_id,
                    aggregate_id=row.aggregate_id,
                    broker_order_id=int(row.broker_order_id),
                    symbol=row.symbol,
                    security_type=row.security_type,
                    side=row.side,
                    quantity=float(row.quantity),
                    price=float(row.price),
                    commission=float(row.commission or 0.0),
                    currency=row.currency,
                    exchange=row.exchange,
                    executed_at=row.executed_at,
                    contract_id=int(row.contract_id or 0),
                    permanent_id=int(row.permanent_id or 0),
                    metadata={
                        "settled": bool(row.settled),
                        "imported_at": row.imported_at,
                    },
                )
                for row in rows
            )
        finally:
            session.close()
