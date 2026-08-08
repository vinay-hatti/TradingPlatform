from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from trading_ai.broker.ibkr.database_models import (
    BrokerAccountBindingModel,
    BrokerAccountSnapshotModel,
    BrokerPositionSnapshotModel,
)
from trading_ai.broker.ibkr.reconciliation import IbkrPaperReconciliationService
from trading_ai.broker.ibkr.service import IbkrPaperAccountService
from trading_ai.broker.ibkr.transport import IbapiTransport, IbkrTransport
from trading_ai.portfolio_intelligence.contracts import PositionMark
from trading_ai.portfolio_intelligence.models import ManagedPositionModel, PortfolioSnapshotModel
from trading_ai.portfolio_intelligence.service import PortfolioIntelligenceService
from trading_ai.portfolio_management.database_models import PortfolioPositionModel

from .models import (
    BrokerCurrentPositionModel,
    BrokerPortfolioAlertModel,
    BrokerPortfolioPublicationModel,
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(prefix: str, value: str) -> str:
    return prefix + hashlib.sha256(value.encode()).hexdigest()[:24].upper()


class BrokerPortfolioSynchronizationService:
    """Authoritative IBKR-to-portfolio synchronization and reconciliation.

    Broker snapshots remain immutable. This service projects the newest snapshot
    into a canonical current-position table, reconciles local portfolio and
    managed-position state, and publishes a broker-backed Portfolio Intelligence
    snapshot. Repeated runs are idempotent.
    """

    def __init__(
        self,
        session_factory: Callable,
        transport: IbkrTransport | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.transport = transport

    def synchronize(
        self,
        portfolio_id: str = "PAPER-PRIMARY",
        *,
        actor: str = "m63-broker-sync",
        connect_broker: bool = True,
    ) -> dict:
        account_sync: dict | None = None
        if connect_broker:
            account_sync = IbkrPaperAccountService(
                self.session_factory,
                self.transport or IbapiTransport(),
            ).verify_and_sync(portfolio_id)

        # Preserve the existing reconciliation report and legacy import behavior.
        reconciliation = IbkrPaperReconciliationService(self.session_factory).reconcile(
            portfolio_id,
            import_positions=False,
        )

        with self.session_factory() as session:
            try:
                result = self._project(session, portfolio_id, actor, reconciliation)
                session.commit()
            except Exception:
                session.rollback()
                raise
        portfolio_intelligence = None
        try:
            from trading_ai.portfolio_risk_allocation.orchestration import (
                Milestone64ContinuousPortfolioIntelligenceService,
            )
            portfolio_intelligence = Milestone64ContinuousPortfolioIntelligenceService(
                self.session_factory
            ).run(portfolio_id, actor=f"{actor}:m64")
        except Exception as exc:  # Broker truth must remain publishable if analytics are unavailable.
            portfolio_intelligence = {
                "status": "DEGRADED",
                "error": f"{type(exc).__name__}: {exc}",
            }
        return {
            "account_sync": account_sync,
            "reconciliation": reconciliation,
            "portfolio_intelligence": portfolio_intelligence,
            **result,
        }

    def _project(self, session: Session, portfolio_id: str, actor: str, reconciliation: dict) -> dict:
        binding = session.scalar(
            select(BrokerAccountBindingModel).where(
                BrokerAccountBindingModel.portfolio_id == portfolio_id
            )
        )
        if binding is None:
            raise LookupError(f"No IBKR binding registered for {portfolio_id}")

        account = session.scalar(
            select(BrokerAccountSnapshotModel)
            .where(BrokerAccountSnapshotModel.portfolio_id == portfolio_id)
            .order_by(BrokerAccountSnapshotModel.captured_at.desc())
            .limit(1)
        )
        if account is None:
            raise LookupError(f"No IBKR account snapshot available for {portfolio_id}")

        snapshot_positions = list(
            session.scalars(
                select(BrokerPositionSnapshotModel).where(
                    BrokerPositionSnapshotModel.account_snapshot_id == account.snapshot_id
                )
            ).all()
        )
        current_rows = list(
            session.scalars(
                select(BrokerCurrentPositionModel).where(
                    BrokerCurrentPositionModel.portfolio_id == portfolio_id
                )
            ).all()
        )
        by_contract = {row.contract_id: row for row in current_rows}
        seen: set[int] = set()
        imported = updated = closed = managed_created = 0
        matched = broker_discovered = drift = 0
        alerts: list[dict] = []

        for broker in snapshot_positions:
            seen.add(broker.contract_id)
            row = by_contract.get(broker.contract_id)
            provenance, lineage = self._resolve_provenance(session, portfolio_id, broker)
            reconciliation_status = "MATCHED" if provenance == "INSTITUTIONAL_OPTIONS" else "BROKER_DISCOVERED"
            if row is None:
                row = BrokerCurrentPositionModel(
                    broker_position_id=stable_id(
                        "BCP-", f"{portfolio_id}|{binding.broker_account_id}|{broker.contract_id}"
                    ),
                    portfolio_id=portfolio_id,
                    binding_id=binding.binding_id,
                    broker_account_id=binding.broker_account_id,
                    account_snapshot_id=account.snapshot_id,
                    contract_id=broker.contract_id,
                    symbol=broker.symbol,
                    local_symbol=broker.local_symbol,
                    security_type=broker.security_type,
                    currency=broker.currency,
                    exchange=broker.exchange,
                    signed_quantity=broker.quantity,
                    average_cost=broker.average_cost,
                    market_price=broker.average_cost,
                    market_value=abs(broker.quantity) * broker.average_cost * (broker.multiplier or 1.0),
                    unrealized_pnl=0.0,
                    realized_pnl=0.0,
                    expiry=broker.expiry,
                    strike=broker.strike,
                    right=broker.right,
                    multiplier=broker.multiplier,
                    active=True,
                    provenance=provenance,
                    reconciliation_status=reconciliation_status,
                    first_seen_at=broker.captured_at,
                    last_seen_at=broker.captured_at,
                    closed_at=None,
                    raw_json={**(broker.raw_json or {}), "lineage": lineage},
                )
                session.add(row)
                imported += 1
            else:
                if row.signed_quantity != broker.quantity:
                    reconciliation_status = "QUANTITY_REFRESHED"
                    drift += 1
                row.account_snapshot_id = account.snapshot_id
                row.signed_quantity = broker.quantity
                row.average_cost = broker.average_cost
                row.market_price = row.market_price or broker.average_cost
                row.market_value = abs(broker.quantity) * (row.market_price or broker.average_cost) * (broker.multiplier or 1.0)
                row.symbol = broker.symbol
                row.local_symbol = broker.local_symbol
                row.expiry = broker.expiry
                row.strike = broker.strike
                row.right = broker.right
                row.multiplier = broker.multiplier
                row.active = broker.quantity != 0
                row.provenance = provenance
                row.reconciliation_status = reconciliation_status
                row.last_seen_at = broker.captured_at
                row.closed_at = None if broker.quantity != 0 else broker.captured_at
                row.raw_json = {**(broker.raw_json or {}), "lineage": lineage}
                updated += 1

            portfolio_position = self._upsert_portfolio_position(session, row, lineage)
            row.portfolio_position_id = portfolio_position.position_id
            managed = self._upsert_managed_position(session, row, lineage, actor)
            if managed is not None:
                if row.managed_position_id is None:
                    managed_created += 1
                row.managed_position_id = managed.position_id
            if provenance == "INSTITUTIONAL_OPTIONS":
                matched += 1
            else:
                broker_discovered += 1
                alerts.append({
                    "type": "BROKER_DISCOVERED_POSITION",
                    "symbol": row.symbol,
                    "contract_id": row.contract_id,
                    "message": "Position exists at IBKR without complete platform decision lineage",
                })
                self._upsert_alert(session, portfolio_id, row, alerts[-1])

        for row in current_rows:
            if row.contract_id in seen or not row.active:
                continue
            row.active = False
            row.reconciliation_status = "CLOSED_AT_BROKER"
            row.closed_at = account.captured_at
            row.last_seen_at = account.captured_at
            closed += 1
            if row.portfolio_position_id:
                local = session.get(PortfolioPositionModel, row.portfolio_position_id)
                if local is not None:
                    local.status = "CLOSED"
                    local.closed_at = account.captured_at
                    local.updated_at = account.captured_at
            if row.managed_position_id:
                managed = session.get(ManagedPositionModel, row.managed_position_id)
                if managed is not None and managed.state not in {"CLOSED", "CANCELLED"}:
                    managed.state = "CLOSED"
                    managed.closed_at = account.captured_at
                    managed.updated_at = account.captured_at
                    managed.version += 1

        portfolio_snapshot = self._publish_portfolio_snapshot(session, portfolio_id, account, actor)
        publication = BrokerPortfolioPublicationModel(
            publication_id=f"M63-PUB-{uuid4().hex.upper()}",
            publication_name="current_broker_portfolio",
            portfolio_id=portfolio_id,
            broker_account_id=binding.broker_account_id,
            account_snapshot_id=account.snapshot_id,
            reconciliation_run_id=reconciliation["run_id"],
            status="READY" if drift == 0 else "DEGRADED",
            position_count=len(snapshot_positions),
            matched_count=matched,
            broker_discovered_count=broker_discovered,
            drift_count=drift,
            published_at=now(),
            payload_json={
                "net_liquidation": account.net_liquidation,
                "cash": account.total_cash_value,
                "buying_power": account.buying_power,
                "available_funds": account.available_funds,
                "positions_imported": imported,
                "positions_updated": updated,
                "positions_closed": closed,
                "managed_positions_created": managed_created,
                "portfolio_snapshot_id": portfolio_snapshot.snapshot_id,
                "alerts": alerts,
            },
        )
        session.add(publication)
        return {
            "status": publication.status,
            "portfolio_id": portfolio_id,
            "publication": "current_broker_portfolio",
            "publication_id": publication.publication_id,
            "account_snapshot_id": account.snapshot_id,
            "broker_position_count": len(snapshot_positions),
            "positions_imported": imported,
            "positions_updated": updated,
            "positions_closed": closed,
            "matched_positions": matched,
            "broker_discovered_positions": broker_discovered,
            "managed_positions_created": managed_created,
            "drift_count": drift,
            "alerts": alerts,
            "portfolio_snapshot_id": portfolio_snapshot.snapshot_id,
        }

    @staticmethod
    def _resolve_provenance(session: Session, portfolio_id: str, broker: BrokerPositionSnapshotModel) -> tuple[str, dict]:
        # Search managed positions for exact contract identity retained by M62.
        managed_rows = list(
            session.scalars(
                select(ManagedPositionModel).where(
                    ManagedPositionModel.portfolio_id == portfolio_id,
                    ManagedPositionModel.symbol == broker.symbol,
                    ManagedPositionModel.state.notin_(["CLOSED", "CANCELLED"]),
                )
            ).all()
        )
        for managed in managed_rows:
            metadata = managed.metadata_json or {}
            dynamic = metadata.get("dynamic_management", {}) or {}
            serialized = str({"metadata": metadata, "dynamic": dynamic})
            if str(broker.contract_id) in serialized or (broker.local_symbol and broker.local_symbol in serialized):
                return "INSTITUTIONAL_OPTIONS", {
                    "managed_position_id": managed.position_id,
                    "trade_plan_id": managed.trade_plan_id,
                    "opportunity_id": managed.opportunity_id,
                    "decision_snapshot_id": metadata.get("decision_snapshot_id"),
                    "decision_state_hash": metadata.get("decision_state_hash"),
                }
        return "BROKER_DISCOVERED", {}

    @staticmethod
    def _upsert_portfolio_position(session: Session, row: BrokerCurrentPositionModel, lineage: dict) -> PortfolioPositionModel:
        position_id = stable_id("IBKR-POS-", f"{row.portfolio_id}|{row.contract_id}")
        local = session.get(PortfolioPositionModel, position_id)
        quantity = int(round(abs(row.signed_quantity)))
        direction = "LONG" if row.signed_quantity >= 0 else "SHORT"
        payload = {
            "broker": "INTERACTIVE_BROKERS",
            "broker_environment": "PAPER",
            "broker_account_id": row.broker_account_id,
            "broker_contract_id": row.contract_id,
            "broker_signed_quantity": row.signed_quantity,
            "local_symbol": row.local_symbol,
            "security_type": row.security_type,
            "currency": row.currency,
            "exchange": row.exchange,
            "expiry": row.expiry,
            "strike": row.strike,
            "right": row.right,
            "multiplier": row.multiplier,
            "provenance": row.provenance,
            "reconciliation_status": row.reconciliation_status,
            "m62_lineage": lineage,
            "authoritative_source": "IBKR_CURRENT_POSITION",
        }
        if local is None:
            local = PortfolioPositionModel(
                position_id=position_id,
                portfolio_id=row.portfolio_id,
                symbol=row.symbol,
                strategy_id=f"IBKR:{row.local_symbol or row.contract_id}",
                strategy_type="BROKER_SYNCED_OPTION" if row.security_type == "OPT" else "BROKER_SYNCED",
                direction=direction,
                status="OPEN" if row.active else "CLOSED",
                quantity=quantity,
                entry_price=row.average_cost,
                current_price=row.market_price or row.average_cost,
                capital_committed=abs(row.signed_quantity) * row.average_cost * (row.multiplier or 1.0),
                maximum_loss=None,
                maximum_profit=None,
                realized_pnl=row.realized_pnl,
                unrealized_pnl=row.unrealized_pnl,
                opened_at=row.first_seen_at,
                updated_at=row.last_seen_at,
                closed_at=row.closed_at,
                sector="UNKNOWN",
                industry="UNKNOWN",
                correlation_group="",
                delta=0.0,
                gamma=0.0,
                theta=0.0,
                vega=0.0,
                rho=0.0,
                source_artifact="M63_IBKR_BROKER_SYNC",
                metadata_json=payload,
            )
            session.add(local)
        else:
            local.symbol = row.symbol
            local.direction = direction
            local.status = "OPEN" if row.active else "CLOSED"
            local.quantity = quantity
            local.entry_price = row.average_cost
            local.current_price = row.market_price or row.average_cost
            local.capital_committed = abs(row.signed_quantity) * row.average_cost * (row.multiplier or 1.0)
            local.unrealized_pnl = row.unrealized_pnl
            local.updated_at = row.last_seen_at
            local.closed_at = row.closed_at
            local.metadata_json = {**(local.metadata_json or {}), **payload}
        return local

    @staticmethod
    def _upsert_managed_position(
        session: Session,
        row: BrokerCurrentPositionModel,
        lineage: dict,
        actor: str,
    ) -> ManagedPositionModel | None:
        managed = None
        lineage_id = lineage.get("managed_position_id")
        if lineage_id:
            managed = session.get(ManagedPositionModel, lineage_id)
        if managed is None:
            candidates = list(session.scalars(select(ManagedPositionModel).where(ManagedPositionModel.portfolio_id == row.portfolio_id)).all())
            managed = next((item for item in candidates if str((item.metadata_json or {}).get("broker_contract_id", "")) == str(row.contract_id)), None)
        mark_price = row.market_price or row.average_cost
        market_value = abs(row.signed_quantity) * mark_price * (row.multiplier or 1.0)
        entry_value = abs(row.signed_quantity) * row.average_cost * (row.multiplier or 1.0)
        mark = PositionMark(
            mark_price=mark_price,
            quantity=abs(row.signed_quantity),
            market_value=market_value,
            unrealized_pnl=row.unrealized_pnl,
            unrealized_return_pct=(row.unrealized_pnl / max(entry_value, 1.0)) * 100.0,
            delta=0.0,
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            days_to_expiry=None,
        )
        health = PortfolioIntelligenceService.health(mark, {"thesis_score": 75})
        decision = PortfolioIntelligenceService.decision(mark, health)
        if managed is None:
            synthetic = row.provenance != "INSTITUTIONAL_OPTIONS"
            managed = ManagedPositionModel(
                position_id=stable_id("MP-IBKR-", f"{row.portfolio_id}|{row.contract_id}"),
                portfolio_id=row.portfolio_id,
                trade_plan_id=lineage.get("trade_plan_id") or f"BROKER-DISCOVERED:{row.contract_id}",
                opportunity_id=lineage.get("opportunity_id") or f"BROKER-DISCOVERED:{row.contract_id}",
                intelligence_id=None,
                execution_id=None,
                symbol=row.symbol,
                strategy="BROKER_DISCOVERED" if synthetic else "INSTITUTIONAL_OPTIONS",
                direction="BULLISH" if row.signed_quantity > 0 else "BEARISH",
                state="OPEN" if row.active else "CLOSED",
                version=1,
                opened_at=row.first_seen_at,
                closed_at=row.closed_at,
                entry_value=entry_value,
                realized_pnl=row.realized_pnl,
                mark_json=mark.__dict__,
                health_json=health.to_dict(),
                decision_json=decision.to_dict(),
                metadata_json={
                    "broker_contract_id": str(row.contract_id),
                    "broker_account_id": row.broker_account_id,
                    "local_symbol": row.local_symbol,
                    "provenance": row.provenance,
                    "reconciliation_status": row.reconciliation_status,
                    "m62_lineage": lineage,
                    "broker_discovered": synthetic,
                    "management_mode": "ADVISORY" if synthetic else "PLATFORM_MANAGED",
                    "automation_mode": "ADVISORY",
                    "sector": "UNCLASSIFIED",
                },
                created_by=actor,
                created_at=now(),
                updated_at=now(),
            )
            session.add(managed)
        else:
            managed.state = "OPEN" if row.active else "CLOSED"
            managed.closed_at = row.closed_at
            managed.mark_json = mark.__dict__
            managed.health_json = health.to_dict()
            managed.decision_json = decision.to_dict()
            managed.updated_at = now()
            managed.version += 1
            managed.metadata_json = {
                **(managed.metadata_json or {}),
                "broker_contract_id": str(row.contract_id),
                "broker_account_id": row.broker_account_id,
                "local_symbol": row.local_symbol,
                "provenance": row.provenance,
                "reconciliation_status": row.reconciliation_status,
                "m62_lineage": lineage or (managed.metadata_json or {}).get("m62_lineage", {}),
                "last_broker_sync": row.last_seen_at,
            }
        return managed

    @staticmethod
    def _publish_portfolio_snapshot(
        session: Session,
        portfolio_id: str,
        account: BrokerAccountSnapshotModel,
        actor: str,
    ) -> PortfolioSnapshotModel:
        active = list(
            session.scalars(
                select(BrokerCurrentPositionModel).where(
                    BrokerCurrentPositionModel.portfolio_id == portfolio_id,
                    BrokerCurrentPositionModel.active.is_(True),
                )
            ).all()
        )
        market_value = sum(row.market_value for row in active)
        unrealized = sum(row.unrealized_pnl for row in active)
        payload = {
            "portfolio_id": portfolio_id,
            "snapshot_timestamp": account.captured_at,
            "net_liquidation": account.net_liquidation,
            "cash": account.total_cash_value,
            "buying_power": account.buying_power,
            "available_funds": account.available_funds,
            "excess_liquidity": account.excess_liquidity,
            "market_value": market_value,
            "unrealized_pnl": unrealized,
            "realized_pnl": sum(row.realized_pnl for row in active),
            "open_risk": sum(abs(row.average_cost * row.signed_quantity * (row.multiplier or 1.0)) for row in active),
            "health_score": 75.0 if active else 100.0,
            "position_count": len(active),
            "greeks": {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0},
            "sector_exposure": {"UNCLASSIFIED": market_value} if active else {},
            "strategy_exposure": {
                "BROKER_SYNCED": market_value,
            } if active else {},
            "concentration": {
                "largest_position_pct": round(
                    max([abs(row.market_value) for row in active] or [0.0]) / max(abs(market_value), 1.0) * 100.0,
                    2,
                ),
                "active_positions": len(active),
            },
            "broker_truth": True,
            "account_snapshot_id": account.snapshot_id,
        }
        snapshot = PortfolioSnapshotModel(
            snapshot_id=f"M63-PS-{uuid4().hex.upper()}",
            portfolio_id=portfolio_id,
            snapshot_timestamp=account.captured_at,
            payload_json=payload,
            generated_by=actor,
        )
        session.add(snapshot)
        return snapshot

    @staticmethod
    def _upsert_alert(session: Session, portfolio_id: str, row: BrokerCurrentPositionModel, alert: dict) -> None:
        existing = session.scalar(
            select(BrokerPortfolioAlertModel).where(
                BrokerPortfolioAlertModel.portfolio_id == portfolio_id,
                BrokerPortfolioAlertModel.broker_position_id == row.broker_position_id,
                BrokerPortfolioAlertModel.alert_type == alert["type"],
                BrokerPortfolioAlertModel.status == "OPEN",
            )
        )
        if existing is None:
            session.add(BrokerPortfolioAlertModel(
                alert_id=f"M63-ALERT-{uuid4().hex.upper()}",
                portfolio_id=portfolio_id,
                broker_position_id=row.broker_position_id,
                severity="WARNING",
                alert_type=alert["type"],
                status="OPEN",
                message=alert["message"],
                created_at=now(),
                resolved_at=None,
                payload_json=alert,
            ))
