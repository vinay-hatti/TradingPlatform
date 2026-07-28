from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select

from trading_ai.portfolio_management.database_models import PortfolioPositionModel
from .database_models import (
    BrokerAccountBindingModel,
    BrokerPositionSnapshotModel,
    BrokerReconciliationRunModel,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, value: str) -> str:
    return prefix + hashlib.sha256(value.encode()).hexdigest()[:24].upper()


class IbkrPaperReconciliationService:
    """Reconciles the latest verified IBKR paper snapshot with local positions."""

    def __init__(self, session_factory: Callable) -> None:
        self.session_factory = session_factory

    def reconcile(self, portfolio_id: str, *, import_positions: bool = True) -> dict:
        started_at = _now()
        session = self.session_factory()
        run_id = _id("IBKR-REC-", f"{portfolio_id}|{started_at}")
        try:
            binding = session.scalar(
                select(BrokerAccountBindingModel).where(
                    BrokerAccountBindingModel.portfolio_id == portfolio_id
                )
            )
            if binding is None:
                raise LookupError(f"No IBKR binding registered for {portfolio_id}")
            if binding.status not in {"VERIFIED_PAPER", "VERIFIED_READ_ONLY"}:
                raise RuntimeError("IBKR binding must be verified before reconciliation")

            latest_snapshot = session.scalar(
                select(BrokerPositionSnapshotModel.account_snapshot_id)
                .where(BrokerPositionSnapshotModel.portfolio_id == portfolio_id)
                .order_by(BrokerPositionSnapshotModel.captured_at.desc())
                .limit(1)
            )
            broker_rows = []
            if latest_snapshot:
                broker_rows = list(
                    session.scalars(
                        select(BrokerPositionSnapshotModel).where(
                            BrokerPositionSnapshotModel.account_snapshot_id == latest_snapshot
                        )
                    ).all()
                )

            local_rows = list(
                session.scalars(
                    select(PortfolioPositionModel).where(
                        PortfolioPositionModel.portfolio_id == portfolio_id,
                        PortfolioPositionModel.status == "OPEN",
                    )
                ).all()
            )
            local_by_contract = {
                str((row.metadata_json or {}).get("broker_contract_id", "")): row
                for row in local_rows
                if (row.metadata_json or {}).get("broker_contract_id") is not None
            }
            broker_by_contract = {str(row.contract_id): row for row in broker_rows}

            differences: list[dict] = []
            imported = 0
            closed = 0
            for contract_id, broker in broker_by_contract.items():
                local = local_by_contract.get(contract_id)
                expected_quantity = int(round(broker.quantity))
                if local is None:
                    differences.append(
                        {
                            "type": "MISSING_LOCAL_POSITION",
                            "contract_id": broker.contract_id,
                            "symbol": broker.symbol,
                            "broker_quantity": broker.quantity,
                        }
                    )
                    if import_positions and expected_quantity != 0:
                        position_id = _id(
                            "IBKR-POS-",
                            f"{portfolio_id}|{broker.contract_id}|{broker.local_symbol}",
                        )
                        direction = "LONG" if expected_quantity > 0 else "SHORT"
                        session.add(
                            PortfolioPositionModel(
                                position_id=position_id,
                                portfolio_id=portfolio_id,
                                symbol=broker.symbol,
                                strategy_id=f"IBKR_IMPORT:{broker.local_symbol or broker.symbol}",
                                strategy_type="BROKER_IMPORTED",
                                direction=direction,
                                status="OPEN",
                                quantity=abs(expected_quantity),
                                entry_price=broker.average_cost,
                                current_price=broker.average_cost,
                                capital_committed=abs(expected_quantity)
                                * broker.average_cost
                                * (broker.multiplier or 1.0),
                                maximum_loss=None,
                                maximum_profit=None,
                                realized_pnl=0.0,
                                unrealized_pnl=0.0,
                                opened_at=broker.captured_at,
                                updated_at=broker.captured_at,
                                closed_at=None,
                                sector="UNKNOWN",
                                industry="UNKNOWN",
                                correlation_group="",
                                delta=0.0,
                                gamma=0.0,
                                theta=0.0,
                                vega=0.0,
                                rho=0.0,
                                source_artifact="IBKR_PAPER_SYNC",
                                metadata_json={
                                    "broker": "INTERACTIVE_BROKERS",
                                    "broker_environment": "PAPER",
                                    "broker_account_id": binding.broker_account_id,
                                    "broker_contract_id": broker.contract_id,
                                    "broker_signed_quantity": broker.quantity,
                                    "local_symbol": broker.local_symbol,
                                    "security_type": broker.security_type,
                                    "currency": broker.currency,
                                    "exchange": broker.exchange,
                                    "expiry": broker.expiry,
                                    "strike": broker.strike,
                                    "right": broker.right,
                                    "multiplier": broker.multiplier,
                                    "read_only_import": True,
                                },
                            )
                        )
                        imported += 1
                    continue

                local_signed = local.quantity if local.direction == "LONG" else -local.quantity
                if local_signed != expected_quantity:
                    differences.append(
                        {
                            "type": "QUANTITY_MISMATCH",
                            "contract_id": broker.contract_id,
                            "symbol": broker.symbol,
                            "broker_quantity": broker.quantity,
                            "local_quantity": local_signed,
                        }
                    )
                    if import_positions:
                        local.direction = "LONG" if expected_quantity >= 0 else "SHORT"
                        local.quantity = abs(expected_quantity)
                        local.updated_at = broker.captured_at
                        local.metadata_json = {
                            **(local.metadata_json or {}),
                            "broker_signed_quantity": broker.quantity,
                            "last_broker_sync": broker.captured_at,
                        }

            for contract_id, local in local_by_contract.items():
                if contract_id in broker_by_contract:
                    continue
                differences.append(
                    {
                        "type": "MISSING_BROKER_POSITION",
                        "contract_id": contract_id,
                        "symbol": local.symbol,
                        "local_quantity": local.quantity,
                    }
                )
                if import_positions and (local.metadata_json or {}).get("read_only_import"):
                    local.status = "CLOSED"
                    local.closed_at = started_at
                    local.updated_at = started_at
                    closed += 1

            completed_at = _now()
            status = "RECONCILED" if not differences else "RECONCILED_WITH_DIFFERENCES"
            session.add(
                BrokerReconciliationRunModel(
                    run_id=run_id,
                    binding_id=binding.binding_id,
                    portfolio_id=portfolio_id,
                    started_at=started_at,
                    completed_at=completed_at,
                    status=status,
                    account_match=True,
                    position_difference_count=len(differences),
                    details_json={
                        "broker_snapshot_id": latest_snapshot,
                        "broker_position_count": len(broker_rows),
                        "local_open_position_count": len(local_rows),
                        "positions_imported": imported,
                        "positions_closed": closed,
                        "differences": differences,
                    },
                    error_text="",
                )
            )
            session.commit()
            return {
                "run_id": run_id,
                "status": status,
                "portfolio_id": portfolio_id,
                "broker_position_count": len(broker_rows),
                "local_open_position_count_before": len(local_rows),
                "position_difference_count": len(differences),
                "positions_imported": imported,
                "positions_closed": closed,
                "differences": differences,
            }
        except Exception as exc:
            session.rollback()
            try:
                binding = session.scalar(
                    select(BrokerAccountBindingModel).where(
                        BrokerAccountBindingModel.portfolio_id == portfolio_id
                    )
                )
                if binding is not None:
                    session.add(
                        BrokerReconciliationRunModel(
                            run_id=run_id,
                            binding_id=binding.binding_id,
                            portfolio_id=portfolio_id,
                            started_at=started_at,
                            completed_at=_now(),
                            status="FAILED",
                            account_match=False,
                            position_difference_count=0,
                            details_json={},
                            error_text=str(exc),
                        )
                    )
                    session.commit()
            except Exception:
                session.rollback()
            raise
        finally:
            session.close()
