from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.execution_workspace.models import ExecutionIntentAuditModel, ExecutionIntentModel
from trading_ai.broker.ibkr.database_models import (
    BrokerAccountBindingModel,
    BrokerAccountSnapshotModel,
    BrokerPositionSnapshotModel,
    BrokerOrderModel,
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


def _normalized_broker_unit_price(security_type: str, raw_average_cost: float, multiplier: float | None) -> float:
    """Normalize IBKR position avgCost into per-unit price semantics used by the platform.

    IBKR reports option position avgCost in contract-currency units (premium * multiplier).
    Platform position prices are per option-share premium units and apply multiplier exactly once
    when computing market/capital value.
    """
    raw=float(raw_average_cost or 0.0)
    mult=float(multiplier or 1.0)
    if str(security_type or '').upper()=='OPT' and mult>1.0:
        return raw/mult
    return raw


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
        m73_management = None
        try:
            from trading_ai.autonomous_position_management import AutonomousPositionManagementService, load_m73_policy
            if load_m73_policy().enabled:
                with self.session_factory() as m73_session:
                    m73_management = AutonomousPositionManagementService(m73_session).ensure_managers(portfolio_id, actor=f"{actor}:m73")
        except Exception as exc:
            m73_management = {"status":"DEGRADED","error":f"{type(exc).__name__}: {exc}"}
        # M64.2.4: broker truth is latency-sensitive and must never wait behind
        # portfolio analytics.  The dedicated M64 LaunchAgent consumes the
        # current_broker_portfolio publication on its own governed schedule.
        # This also keeps M73 fill/position bootstrap responsive because that
        # workflow legitimately calls broker synchronization synchronously.
        portfolio_intelligence = {
            "status": "DEFERRED_TO_DEDICATED_SCHEDULER",
            "blocking": False,
            "scheduler_label": "com.tradingplatform.m64-portfolio-intelligence",
            "source_publication": "current_broker_portfolio",
            "source_publication_id": result.get("publication_id"),
            "reason": "BROKER_TRUTH_PUBLISHED_WITHOUT_SYNCHRONOUS_M64_EXECUTION",
        }
        return {
            "account_sync": account_sync,
            "reconciliation": reconciliation,
            "m73_management": m73_management,
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

        # M74.6 recovery covers platform-originated BAGs that reached TWS before
        # the historical submit path durably persisted broker_orders. Recovery is
        # exact-full-leg-set only; ambiguous/partial matches remain broker-discovered.
        recovered_lineage_by_contract = self._recover_platform_intent_lineages(
            session, portfolio_id, snapshot_positions, current_rows
        )

        for broker in snapshot_positions:
            seen.add(broker.contract_id)
            row = by_contract.get(broker.contract_id)
            normalized_cost = _normalized_broker_unit_price(broker.security_type, broker.average_cost, broker.multiplier)
            recovered_lineage = recovered_lineage_by_contract.get(int(broker.contract_id))
            if recovered_lineage:
                provenance, lineage = "INSTITUTIONAL_OPTIONS", dict(recovered_lineage)
            else:
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
                    average_cost=normalized_cost,
                    market_price=normalized_cost,
                    market_value=abs(broker.quantity) * normalized_cost * (broker.multiplier or 1.0),
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
                    raw_json={**(broker.raw_json or {}), "lineage": lineage, "pricing_normalization": {"raw_ibkr_average_cost": broker.average_cost, "normalized_unit_price": normalized_cost, "multiplier": broker.multiplier, "basis": "IBKR_OPTION_AVGCOST_DIVIDED_BY_MULTIPLIER" if str(broker.security_type).upper()=="OPT" and float(broker.multiplier or 1)>1 else "AS_REPORTED"}},
                )
                session.add(row)
                imported += 1
            else:
                if row.signed_quantity != broker.quantity:
                    reconciliation_status = "QUANTITY_REFRESHED"
                    drift += 1
                row.account_snapshot_id = account.snapshot_id
                row.signed_quantity = broker.quantity
                row.average_cost = normalized_cost
                # Broker position snapshots do not provide a trustworthy live option mark here.
                # Keep current-position price in the same normalized unit as average_cost; M73
                # obtains fresh executable marks directly from Polygon for management decisions.
                row.market_price = normalized_cost
                row.market_value = abs(broker.quantity) * normalized_cost * (broker.multiplier or 1.0)
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
                row.raw_json = {**(broker.raw_json or {}), "lineage": lineage, "pricing_normalization": {"raw_ibkr_average_cost": broker.average_cost, "normalized_unit_price": normalized_cost, "multiplier": broker.multiplier, "basis": "IBKR_OPTION_AVGCOST_DIVIDED_BY_MULTIPLIER" if str(broker.security_type).upper()=="OPT" and float(broker.multiplier or 1)>1 else "AS_REPORTED"}}
                updated += 1

            portfolio_position = self._upsert_portfolio_position(session, row, lineage)
            row.portfolio_position_id = portfolio_position.position_id
            previous_managed_position_id = row.managed_position_id
            managed = self._upsert_managed_position(session, row, lineage, actor)
            if managed is not None:
                if row.managed_position_id is None:
                    managed_created += 1
                row.managed_position_id = managed.position_id
                if previous_managed_position_id and previous_managed_position_id != managed.position_id:
                    self._retire_superseded_managed_projection(
                        session,
                        previous_managed_position_id,
                        managed.position_id,
                        row,
                        actor,
                    )
            if provenance == "INSTITUTIONAL_OPTIONS":
                matched += 1
                self._resolve_alert(
                    session,
                    portfolio_id,
                    row,
                    "BROKER_DISCOVERED_POSITION",
                    reason="Canonical managed-position lineage recovered",
                )
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

        self._aggregate_institutional_managed_positions(session, portfolio_id)
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
    def _parse_iso(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None

    @classmethod
    def _broker_matches_plan_leg(cls, broker: BrokerPositionSnapshotModel, leg: dict, plan_symbol: str) -> bool:
        broker_occ = cls._normalize_option_symbol(broker.local_symbol)
        leg_occ = cls._normalize_option_symbol(leg.get("option_symbol") or leg.get("local_symbol") or leg.get("ibkr_local_symbol"))
        if broker_occ and leg_occ and broker_occ == leg_occ:
            return True
        symbol = str(leg.get("symbol") or plan_symbol or "").upper()
        expiry = cls._normalize_expiry(leg.get("expiry"))
        right = cls._normalize_right(leg.get("option_right") or leg.get("right"))
        try:
            strike = float(leg.get("strike"))
            broker_strike = float(broker.strike)
        except (TypeError, ValueError):
            return False
        return bool(
            symbol == str(broker.symbol or "").upper()
            and expiry == cls._normalize_expiry(broker.expiry)
            and right == cls._normalize_right(broker.right)
            and abs(strike - broker_strike) < 1e-9
        )

    @staticmethod
    def _broker_order_has_fill(order: BrokerOrderModel | None) -> bool:
        if order is None:
            return False
        status = str(order.status or "").upper().replace(" ", "")
        if status == "FILLED":
            return True
        try:
            filled = float(order.filled_quantity or 0.0)
            quantity = float(order.quantity or 0.0)
            remaining = float(order.remaining_quantity or 0.0)
        except (TypeError, ValueError):
            return False
        return filled > 0 and (remaining <= 0 or (quantity > 0 and filled >= quantity))

    @staticmethod
    def _broker_order_for_intent_from_rows(intent: ExecutionIntentModel, rows: list[BrokerOrderModel]) -> BrokerOrderModel | None:
        token = str(intent.execution_intent_id)
        matches = []
        for order in rows:
            raw = dict(order.raw_json or {})
            req = dict(raw.get("request") or {})
            meta = dict(req.get("metadata") or {})
            explicit = str(meta.get("execution_intent_id") or "") == token
            aggregate = token in str(order.aggregate_id or "") or token in str(order.client_order_id or "")
            if explicit or aggregate:
                matches.append(order)
        if not matches:
            return None
        # Prefer actual fill evidence, then the most recently updated platform order.
        matches.sort(key=lambda x: (1 if BrokerPortfolioSynchronizationService._broker_order_has_fill(x) else 0, str(x.updated_at or "")), reverse=True)
        return matches[0]

    @classmethod
    def _recover_platform_intent_lineages(
        cls, session: Session, portfolio_id: str, snapshot_positions: list[BrokerPositionSnapshotModel], current_rows: list[BrokerCurrentPositionModel]
    ) -> dict[int, dict]:
        """Resolve broker positions back to platform ownership before classifying them external.

        M74.13 makes durable platform broker-order lineage the primary ownership
        authority.  A broker-confirmed fill is authoritative even when the local
        execution intent is CANCEL_REQUESTED, CANCELLED, REJECTED, or another stale
        terminal state.  Exact full-leg identity/direction/quantity remains a required
        verification gate, and ambiguous multiple filled attempts continue to fail
        closed.  Historical position-only recovery remains a weaker fallback.
        """
        current_by_contract = {int(x.contract_id): x for x in current_rows}
        window_hours = max(1.0, float(os.getenv("TRADING_AI_M74_6_RECOVERY_WINDOW_HOURS", "12")))
        pre_tolerance_minutes = max(0.0, float(os.getenv("TRADING_AI_M74_6_RECOVERY_PREINTENT_TOLERANCE_MINUTES", "15")))

        intents = list(session.scalars(
            select(ExecutionIntentModel).where(
                ExecutionIntentModel.portfolio_id == portfolio_id,
            ).order_by(ExecutionIntentModel.created_at.desc())
        ).all())
        broker_orders = list(session.scalars(
            select(BrokerOrderModel).where(BrokerOrderModel.portfolio_id == portfolio_id)
        ).all())
        weak_states = {"APPROVED", "SUBMITTED", "ACKNOWLEDGED", "PARTIALLY_FILLED", "FILLED", "REJECTED"}
        candidates = []

        for intent in intents:
            broker_order = cls._broker_order_for_intent_from_rows(intent, broker_orders)
            broker_fill_truth = cls._broker_order_has_fill(broker_order)
            local_state = str(intent.state or "").upper()
            # Strong broker-order ownership evidence may recover any stale local
            # state.  Without it, preserve the narrow historical recovery states.
            if local_state == "REJECTED" and not broker_fill_truth:
                continue
            if not broker_fill_truth and local_state not in weak_states:
                continue
            tp = session.get(TradePlanModel, intent.trade_plan_id)
            if tp is None or str(tp.account_id or "") != str(portfolio_id):
                continue
            legs = [x for x in list(intent.legs_json or tp.legs_json or []) if isinstance(x, dict)]
            if not legs:
                continue
            created = cls._parse_iso(intent.created_at)
            matches = []
            used_contracts = set()
            valid = True
            for leg in legs:
                side = str(leg.get("side") or "BUY").upper()
                leg_qty = max(1.0, abs(float(leg.get("quantity") or 1.0)))
                rows = []
                for broker in snapshot_positions:
                    cid = int(broker.contract_id)
                    if cid in used_contracts or not cls._broker_matches_plan_leg(broker, leg, tp.symbol):
                        continue
                    signed = float(broker.quantity or 0.0)
                    if signed == 0 or (side == "BUY" and signed < 0) or (side == "SELL" and signed > 0):
                        continue
                    # Explicit filled platform-order lineage does not expire merely
                    # because portfolio projection happened late.  Time proximity is
                    # only needed for weaker position-only inference.
                    if not broker_fill_truth:
                        first_seen = cls._parse_iso((current_by_contract.get(cid).first_seen_at if current_by_contract.get(cid) else broker.captured_at))
                        if created and first_seen:
                            delta = first_seen - created
                            if delta < -timedelta(minutes=pre_tolerance_minutes) or delta > timedelta(hours=window_hours):
                                continue
                    rows.append(broker)
                if len(rows) != 1:
                    valid = False
                    break
                broker = rows[0]
                used_contracts.add(int(broker.contract_id))
                matches.append((leg, broker, abs(float(broker.quantity or 0.0)) / leg_qty))
            if not valid or len(matches) != len(legs):
                continue
            units = [x[2] for x in matches]
            spread_units = min(units) if units else 0.0
            if spread_units <= 0 or max(units) - min(units) > 1e-9 or abs(spread_units - round(spread_units)) > 1e-9:
                continue
            candidates.append({
                "intent": intent,
                "tp": tp,
                "matches": matches,
                "contract_ids": tuple(sorted(int(x[1].contract_id) for x in matches)),
                "spread_units": int(round(spread_units)),
                "broker_order": broker_order,
                "broker_fill_truth": broker_fill_truth,
            })

        # Strong broker-filled ownership outranks weaker position-only inference.
        strong = [rec for rec in candidates if rec["broker_fill_truth"]]
        weak = [rec for rec in candidates if not rec["broker_fill_truth"]]
        strong_contracts = {cid for rec in strong for cid in rec["contract_ids"]}
        effective = strong + [rec for rec in weak if not any(cid in strong_contracts for cid in rec["contract_ids"])]

        contract_owners: dict[int, set[str]] = {}
        for rec in effective:
            for cid in rec["contract_ids"]:
                contract_owners.setdefault(cid, set()).add(rec["tp"].trade_plan_id)

        # Multiple broker-filled retry attempts for one plan remain genuinely
        # ambiguous (the FANG case) and must not be auto-owned.
        grouped_by_plan: dict[str, list[dict]] = {}
        for rec in effective:
            grouped_by_plan.setdefault(rec["tp"].trade_plan_id, []).append(rec)
        by_plan = {}
        for tp_id, recs in grouped_by_plan.items():
            broker_filled = [r for r in recs if r["broker_fill_truth"]]
            if len(broker_filled) > 1:
                continue
            pool = broker_filled or recs
            by_plan[tp_id] = max(pool, key=lambda r: int(r["intent"].execution_attempt or 1))

        recovered: dict[int, dict] = {}
        for rec in by_plan.values():
            if any(len(contract_owners.get(cid, set())) > 1 for cid in rec["contract_ids"]):
                continue
            intent, tp, matches = rec["intent"], rec["tp"], rec["matches"]
            broker_order = rec.get("broker_order")
            broker_fill_truth = bool(rec.get("broker_fill_truth"))
            existing_managed = session.scalar(select(ManagedPositionModel).where(
                ManagedPositionModel.portfolio_id == portfolio_id,
                ManagedPositionModel.trade_plan_id == tp.trade_plan_id,
                ManagedPositionModel.state.notin_(["CLOSED", "CANCELLED", "SUPERSEDED"]),
            ))
            dynamic = dict((intent.metadata_json or {}).get("dynamic_management") or (tp.execution_intent_json or {}).get("dynamic_management") or {})
            contract_ids = list(rec["contract_ids"])
            ratios = {str(int(x[1].contract_id)): max(1, int(round(abs(float(x[0].get("quantity") or 1.0))))) for x in matches}
            verified_at = now()
            authority = "BROKER_ORDER_FILLED_EXACT_LINEAGE" if broker_fill_truth else "EXACT_POSITION_LINEAGE_RECOVERY"
            ownership = {
                "origin": "PLATFORM",
                "owner": "EXECUTION_WORKSPACE",
                "status": "VERIFIED",
                "lifecycle": "AUTONOMOUS",
                "bootstrap_state": "AUTO_BOOTSTRAPPING",
                "authority": authority,
                "trade_plan_id": tp.trade_plan_id,
                "execution_intent_id": intent.execution_intent_id,
                "broker_order_record_id": getattr(broker_order, "broker_order_record_id", None),
                "broker_order_id": getattr(broker_order, "broker_order_id", None),
                "permanent_id": getattr(broker_order, "permanent_id", None),
                "verified_at": verified_at,
            }
            common = {
                "managed_position_id": existing_managed.position_id if existing_managed else None,
                "trade_plan_id": tp.trade_plan_id,
                "opportunity_id": tp.opportunity_id,
                "intelligence_id": tp.intelligence_id,
                "execution_intent_id": intent.execution_intent_id,
                "strategy": tp.strategy,
                "direction": tp.direction,
                "decision_snapshot_id": (intent.metadata_json or {}).get("decision_snapshot_id") or (tp.execution_intent_json or {}).get("decision_snapshot_id"),
                "decision_state_hash": (intent.metadata_json or {}).get("decision_state_hash") or (tp.execution_intent_json or {}).get("decision_state_hash"),
                "dynamic_management": dynamic,
                "automation_mode": "FULLY_AUTOMATIC",
                "identity_match": authority,
                "recovery_source": "M74.13_PLATFORM_OWNERSHIP_RECONCILIATION",
                "broker_contract_ids": contract_ids,
                "broker_leg_ratios": ratios,
                "spread_quantity": rec["spread_units"],
                "position_ownership": ownership,
            }
            for _, broker, _ in matches:
                recovered[int(broker.contract_id)] = dict(common)

            if intent.state != "FILLED":
                previous = intent.state
                intent.version += 1
                intent.state = "FILLED"
                intent.submitted_at = intent.submitted_at or min([str(x[1].captured_at) for x in matches])
                intent.updated_at = verified_at
                intent.terminal_at = verified_at
                recovery_payload = {
                    "source": authority,
                    "contract_ids": contract_ids,
                    "spread_quantity": rec["spread_units"],
                    "recovered_at": verified_at,
                    "broker_order_id": getattr(broker_order, "broker_order_id", None),
                    "permanent_id": getattr(broker_order, "permanent_id", None),
                    "broker_order_status": getattr(broker_order, "status", None),
                    "broker_truth_overrode_local_state": broker_fill_truth and previous != "FILLED",
                    "broker_truth_overrode_local_terminal_state": broker_fill_truth and str(previous or "").upper() in {"REJECTED", "CANCELLED", "CANCELED", "CANCEL_REQUESTED"},
                    "previous_local_state": previous,
                }
                broker_json = {**dict(intent.broker_json or {}), "m74_13_position_ownership_reconciliation": recovery_payload}
                if broker_fill_truth and str(previous or "").upper() == "REJECTED":
                    broker_json["m74_8_broker_truth_reconciliation"] = recovery_payload
                intent.broker_json = broker_json
                intent.metadata_json = {**dict(intent.metadata_json or {}), "position_ownership": ownership}
                if broker_fill_truth and str(previous or "").upper() == "REJECTED":
                    event_type = "BROKER_FILLED_AFTER_LOCAL_REJECTION"
                    reason = "Broker FILLED truth superseded stale local REJECTED state"
                elif broker_fill_truth:
                    event_type = "BROKER_TRUTH_PLATFORM_OWNERSHIP_RECONCILED"
                    reason = "Broker-confirmed platform fill established canonical position ownership"
                else:
                    event_type = "BROKER_POSITION_LINEAGE_RECOVERED"
                    reason = "Recovered platform lineage from exact broker position leg set"
                session.add(ExecutionIntentAuditModel(
                    event_id=f"XEA-{uuid4().hex.upper()}",
                    execution_intent_id=intent.execution_intent_id,
                    execution_intent_version=intent.version,
                    event_type=event_type,
                    previous_state=previous,
                    new_state="FILLED",
                    actor="M74_13_OWNERSHIP_RECONCILIATION",
                    reason=reason,
                    event_timestamp=verified_at,
                    payload_json={**recovery_payload, "trade_plan_id": tp.trade_plan_id, "position_ownership": ownership},
                ))
            else:
                intent.metadata_json = {**dict(intent.metadata_json or {}), "position_ownership": ownership}
        return recovered

    @staticmethod
    def _aggregate_institutional_managed_positions(session: Session, portfolio_id: str) -> None:
        """Aggregate all broker legs of a platform strategy into one managed position."""
        managed_rows = list(session.scalars(select(ManagedPositionModel).where(
            ManagedPositionModel.portfolio_id == portfolio_id,
            ManagedPositionModel.state.in_(["OPEN", "PARTIAL", "HEDGED", "ROLLED"]),
        )).all())
        for managed in managed_rows:
            meta = dict(managed.metadata_json or {})
            if bool(meta.get("broker_discovered")) or str(managed.trade_plan_id or "").startswith("BROKER-DISCOVERED:"):
                continue
            broker_rows = list(session.scalars(select(BrokerCurrentPositionModel).where(
                BrokerCurrentPositionModel.portfolio_id == portfolio_id,
                BrokerCurrentPositionModel.managed_position_id == managed.position_id,
                BrokerCurrentPositionModel.active.is_(True),
            )).all())
            if not broker_rows:
                continue
            tp = session.get(TradePlanModel, managed.trade_plan_id)
            ratios = {}
            if tp is not None:
                for leg in list(tp.legs_json or []):
                    for br in broker_rows:
                        if BrokerPortfolioSynchronizationService._broker_matches_plan_leg(br, leg, tp.symbol):
                            ratios[str(br.contract_id)] = max(1, int(round(abs(float(leg.get("quantity") or 1.0)))))
            units = [abs(float(br.signed_quantity or 0.0)) / max(1, ratios.get(str(br.contract_id), 1)) for br in broker_rows]
            strategy_qty = max(0, int(round(min(units)))) if units else 0
            net_market = sum(float(br.signed_quantity or 0.0) * float(br.market_price or br.average_cost or 0.0) * float(br.multiplier or 1.0) for br in broker_rows)
            net_entry = sum(float(br.signed_quantity or 0.0) * float(br.average_cost or 0.0) * float(br.multiplier or 1.0) for br in broker_rows)
            upnl = sum(float(br.unrealized_pnl or 0.0) for br in broker_rows)
            mark_price = abs(net_market) / max(1, strategy_qty) / 100.0 if strategy_qty else 0.0
            mark = dict(managed.mark_json or {})
            mark.update({"mark_price":mark_price,"quantity":strategy_qty,"market_value":abs(net_market),"unrealized_pnl":upnl,"unrealized_return_pct":upnl/max(abs(net_entry),1.0)*100.0})
            managed.mark_json = mark
            managed.entry_value = abs(net_entry)
            managed.execution_id = managed.execution_id or meta.get("execution_intent_id")
            managed.metadata_json = {**meta, "broker_contract_ids":[int(x.contract_id) for x in broker_rows], "broker_leg_ratios":ratios, "broker_leg_count":len(broker_rows), "broker_strategy_quantity":strategy_qty, "automation_mode":meta.get("automation_mode") or "FULLY_AUTOMATIC", "management_mode":"PLATFORM_MANAGED", "broker_discovered":False}

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
            metadata_match = str(broker.contract_id) in serialized or bool(
                broker.local_symbol and broker.local_symbol in serialized
            )
            trade_plan_id = str(managed.trade_plan_id or "")
            if not trade_plan_id or trade_plan_id.startswith("BROKER-DISCOVERED:"):
                continue
            trade_plan = session.get(TradePlanModel, trade_plan_id)
            if trade_plan is None:
                continue

            # M73.1.0: the original platform-managed POS-* record is created at fill
            # before broker portfolio synchronization has projected broker_contract_id
            # into managed-position metadata. Resolve identity through the immutable
            # trade-plan contract legs as well, otherwise the same fill is rediscovered
            # as a second MP-IBKR-* position.
            identity_match = "MANAGED_METADATA" if metadata_match else BrokerPortfolioSynchronizationService._trade_plan_broker_identity_match(
                trade_plan, broker
            )
            if not identity_match:
                continue
            return "INSTITUTIONAL_OPTIONS", {
                "managed_position_id": managed.position_id,
                "trade_plan_id": managed.trade_plan_id,
                "opportunity_id": managed.opportunity_id,
                "execution_intent_id": managed.execution_id or metadata.get("execution_intent_id"),
                "strategy": managed.strategy,
                "direction": managed.direction,
                "decision_snapshot_id": metadata.get("decision_snapshot_id"),
                "decision_state_hash": metadata.get("decision_state_hash"),
                "dynamic_management": dict(metadata.get("dynamic_management") or (trade_plan.execution_intent_json or {}).get("dynamic_management") or {}),
                "automation_mode": str(metadata.get("automation_mode") or "FULLY_AUTOMATIC"),
                "identity_match": identity_match,
            }
        return "BROKER_DISCOVERED", {}

    @staticmethod
    def _normalize_option_symbol(value: str | None) -> str:
        """Return a canonical Polygon/OCC option identity when possible.

        Trade plans persist Polygon contract tickers (for example
        ``O:TJX260918C00160000``), while IBKR position snapshots persist OCC-style
        local symbols (for example ``TJX   260918C00160000``).  These are the same
        contract identity expressed by different providers.
        """
        raw = str(value or "").strip().upper()
        if not raw:
            return ""
        compact = re.sub(r"\s+", "", raw)
        if compact.startswith("O:"):
            compact = compact[2:]
        if re.fullmatch(r"[A-Z0-9.]{1,8}\d{6}[CP]\d{8}", compact):
            return f"O:{compact}"
        return raw

    @staticmethod
    def _normalize_expiry(value: str | None) -> str:
        raw = str(value or "").strip()
        digits = re.sub(r"[^0-9]", "", raw)
        if len(digits) == 8:
            return digits
        if len(digits) == 6:
            return f"20{digits}"
        return raw

    @staticmethod
    def _normalize_right(value: str | None) -> str:
        raw = str(value or "").strip().upper()
        if raw in {"C", "CALL"}:
            return "C"
        if raw in {"P", "PUT"}:
            return "P"
        return raw

    @staticmethod
    def _trade_plan_broker_identity_match(trade_plan: TradePlanModel, broker: BrokerPositionSnapshotModel) -> str | None:
        """Return the strongest exact identity match between a plan leg and IBKR.

        Precedence deliberately favors broker-native immutable identity, followed by
        provider-normalized OCC identity, then the full option tuple.  The structural
        fallback requires symbol + expiry + strike + right, so symbol-only or
        strike-only coincidences can never adopt a managed position.
        """
        contract_id = str(broker.contract_id or "").strip()
        local_symbol = str(broker.local_symbol or "").strip()
        broker_option_symbol = BrokerPortfolioSynchronizationService._normalize_option_symbol(local_symbol)
        broker_expiry = BrokerPortfolioSynchronizationService._normalize_expiry(broker.expiry)
        broker_right = BrokerPortfolioSynchronizationService._normalize_right(broker.right)
        broker_symbol = str(broker.symbol or "").strip().upper()
        try:
            broker_strike = float(broker.strike) if broker.strike is not None else None
        except (TypeError, ValueError):
            broker_strike = None

        for leg in list(trade_plan.legs_json or []):
            if not isinstance(leg, dict):
                continue
            leg_contract_id = str(leg.get("contract_id") or leg.get("conid") or "").strip()
            if contract_id and leg_contract_id and contract_id == leg_contract_id:
                return "IBKR_CONTRACT_ID"

            leg_local_symbol = str(leg.get("local_symbol") or leg.get("ibkr_local_symbol") or "").strip()
            if local_symbol and leg_local_symbol and re.sub(r"\s+", "", local_symbol.upper()) == re.sub(r"\s+", "", leg_local_symbol.upper()):
                return "IBKR_LOCAL_SYMBOL"

            leg_option_symbol = BrokerPortfolioSynchronizationService._normalize_option_symbol(
                leg.get("option_symbol") or leg_local_symbol
            )
            if broker_option_symbol and leg_option_symbol and broker_option_symbol == leg_option_symbol:
                return "OCC_OPTION_SYMBOL"

            leg_symbol = str(leg.get("symbol") or trade_plan.symbol or "").strip().upper()
            leg_expiry = BrokerPortfolioSynchronizationService._normalize_expiry(leg.get("expiry"))
            leg_right = BrokerPortfolioSynchronizationService._normalize_right(leg.get("option_right") or leg.get("right"))
            try:
                leg_strike = float(leg.get("strike")) if leg.get("strike") is not None else None
            except (TypeError, ValueError):
                leg_strike = None
            tuple_match = (
                broker_symbol
                and leg_symbol == broker_symbol
                and broker_expiry
                and leg_expiry == broker_expiry
                and broker_right
                and leg_right == broker_right
                and broker_strike is not None
                and leg_strike is not None
                and abs(leg_strike - broker_strike) < 1e-9
            )
            if tuple_match:
                return "OPTION_TUPLE"
        return None

    @staticmethod
    def _trade_plan_matches_broker_contract(trade_plan: TradePlanModel, broker: BrokerPositionSnapshotModel) -> bool:
        return BrokerPortfolioSynchronizationService._trade_plan_broker_identity_match(trade_plan, broker) is not None

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
        synthetic = row.provenance != "INSTITUTIONAL_OPTIONS"
        ownership = dict(lineage.get("position_ownership") or {})
        if not ownership:
            ownership = {
                "origin": "EXTERNAL_OR_UNVERIFIED" if synthetic else "PLATFORM",
                "owner": "MANUAL" if synthetic else "EXECUTION_WORKSPACE",
                "status": "UNVERIFIED" if synthetic else "VERIFIED",
                "lifecycle": "MANUAL" if synthetic else "AUTONOMOUS",
                "bootstrap_state": "MANUAL_REQUIRED" if synthetic else "AUTO_BOOTSTRAPPING",
                "authority": "BROKER_DISCOVERY" if synthetic else str(lineage.get("identity_match") or "CANONICAL_LINEAGE"),
                "trade_plan_id": lineage.get("trade_plan_id"),
                "execution_intent_id": lineage.get("execution_intent_id"),
                "verified_at": None if synthetic else now(),
            }

        # M74.6.2: promotion is strategy-level, but _upsert_managed_position is
        # still called once per broker leg.  SQLAlchemy Session.get()/SELECT do
        # not reliably return a ManagedPositionModel that has merely been added
        # to session.new while autoflush is suppressed.  Reuse any pending
        # canonical object first so two legs of the same BAG cannot enqueue two
        # INSERTs with the same deterministic POS-M74-* primary key.
        def _pending_position(position_id: str | None):
            if not position_id:
                return None
            for obj in session.new:
                if isinstance(obj, ManagedPositionModel) and obj.position_id == position_id:
                    return obj
            return None

        lineage_id = lineage.get("managed_position_id")
        if lineage_id:
            candidate = _pending_position(str(lineage_id)) or session.get(ManagedPositionModel, lineage_id)
            if candidate is not None:
                candidate_meta = dict(candidate.metadata_json or {})
                candidate_synthetic = bool(candidate_meta.get("broker_discovered")) or str(candidate.trade_plan_id or "").startswith("BROKER-DISCOVERED:")
                # M74.6.1: never promote a per-leg MP-IBKR projection in place.  A
                # recovered institutional strategy must converge on a canonical
                # strategy-level POS-* record so all broker legs share one manager.
                if synthetic or not candidate_synthetic:
                    managed = candidate
        # M74.6/M74.6.1/M74.6.2: all legs of one institutional strategy must
        # converge to the same canonical managed position, even when only
        # per-leg MP-IBKR projections existed before lineage recovery.  Check
        # session.new before issuing a SELECT so this remains correct inside
        # no_autoflush blocks and batched reconciliation transactions.
        canonical_position_id = None
        if not synthetic and lineage.get("trade_plan_id"):
            canonical_position_id = stable_id(
                "POS-M74-",
                f"{row.portfolio_id}|{lineage.get('trade_plan_id')}|{lineage.get('execution_intent_id') or ''}",
            )
            managed = _pending_position(canonical_position_id)
        if managed is None and lineage.get("trade_plan_id"):
            managed = session.scalar(select(ManagedPositionModel).where(
                ManagedPositionModel.portfolio_id == row.portfolio_id,
                ManagedPositionModel.trade_plan_id == lineage.get("trade_plan_id"),
                ManagedPositionModel.state.notin_(["CLOSED", "CANCELLED", "SUPERSEDED"]),
            ))
        if managed is None and synthetic:
            candidates = list(session.scalars(select(ManagedPositionModel).where(ManagedPositionModel.portfolio_id == row.portfolio_id)).all())
            managed = next((item for item in candidates if str((item.metadata_json or {}).get("broker_contract_id", "")) == str(row.contract_id)), None)
        mark_price = row.market_price or row.average_cost
        market_value = abs(row.signed_quantity) * mark_price * (row.multiplier or 1.0)
        entry_value = abs(row.signed_quantity) * row.average_cost * (row.multiplier or 1.0)
        strategy_qty = int(lineage.get("spread_quantity") or round(abs(row.signed_quantity)) or 1)
        mark = PositionMark(
            mark_price=mark_price,
            quantity=strategy_qty if row.provenance == "INSTITUTIONAL_OPTIONS" else abs(row.signed_quantity),
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
            if synthetic:
                position_id = stable_id("MP-IBKR-", f"{row.portfolio_id}|{row.contract_id}")
            else:
                position_id = canonical_position_id or stable_id("POS-M74-", f"{row.portfolio_id}|{lineage.get('trade_plan_id')}|{lineage.get('execution_intent_id') or ''}")
                # Last-chance idempotency guard: another leg may have queued the
                # canonical object earlier in this same transaction after the
                # previous lookup. Reuse it rather than enqueueing a duplicate.
                pending = _pending_position(position_id)
                if pending is not None:
                    managed = pending
            if managed is not None:
                meta = dict(managed.metadata_json or {})
                contract_ids = set(int(x) for x in (meta.get("broker_contract_ids") or []) if str(x).isdigit())
                contract_ids.add(int(row.contract_id))
                managed.metadata_json = {
                    **meta,
                    "broker_contract_id": str(row.contract_id),
                    "broker_contract_ids": sorted(contract_ids),
                    "broker_leg_ratios": {**dict(meta.get("broker_leg_ratios") or {}), **dict(lineage.get("broker_leg_ratios") or {})},
                    "broker_account_id": row.broker_account_id,
                    "local_symbol": row.local_symbol,
                    "provenance": row.provenance,
                    "reconciliation_status": row.reconciliation_status,
                    "m62_lineage": lineage or meta.get("m62_lineage", {}),
                    "position_ownership": ownership,
                    "execution_intent_id": lineage.get("execution_intent_id") or meta.get("execution_intent_id"),
                    "last_broker_sync": row.last_seen_at,
                    "broker_discovered": False,
                    "management_mode": "PLATFORM_MANAGED",
                    "automation_mode": "FULLY_AUTOMATIC",
                    "dynamic_management": dict(lineage.get("dynamic_management") or meta.get("dynamic_management") or {}),
                    "m74_6_lineage_recovery": meta.get("m74_6_lineage_recovery") or {"source":lineage.get("recovery_source") or lineage.get("identity_match"),"recovered_at":now()},
                }
                managed.trade_plan_id = str(lineage.get("trade_plan_id") or managed.trade_plan_id)
                managed.opportunity_id = str(lineage.get("opportunity_id") or managed.opportunity_id)
                managed.intelligence_id = lineage.get("intelligence_id") or managed.intelligence_id
                managed.strategy = str(lineage.get("strategy") or managed.strategy)
                managed.direction = str(lineage.get("direction") or managed.direction)
                managed.execution_id = lineage.get("execution_intent_id") or managed.execution_id
                managed.state = "OPEN" if row.active else "CLOSED"
                managed.closed_at = row.closed_at
                managed.mark_json = mark.__dict__
                managed.health_json = health.to_dict()
                managed.decision_json = decision.to_dict()
                managed.updated_at = now()
                return managed
            managed = ManagedPositionModel(
                position_id=position_id,
                portfolio_id=row.portfolio_id,
                trade_plan_id=lineage.get("trade_plan_id") or f"BROKER-DISCOVERED:{row.contract_id}",
                opportunity_id=lineage.get("opportunity_id") or f"BROKER-DISCOVERED:{row.contract_id}",
                intelligence_id=lineage.get("intelligence_id"),
                execution_id=lineage.get("execution_intent_id"),
                symbol=row.symbol,
                strategy="BROKER_DISCOVERED" if synthetic else str(lineage.get("strategy") or "INSTITUTIONAL_OPTIONS"),
                direction=("BULLISH" if row.signed_quantity > 0 else "BEARISH") if synthetic else str(lineage.get("direction") or "BULLISH"),
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
                    "broker_contract_ids": list(lineage.get("broker_contract_ids") or [int(row.contract_id)]),
                    "broker_leg_ratios": dict(lineage.get("broker_leg_ratios") or {}),
                    "broker_account_id": row.broker_account_id,
                    "local_symbol": row.local_symbol,
                    "provenance": row.provenance,
                    "reconciliation_status": row.reconciliation_status,
                    "m62_lineage": lineage,
                    "position_ownership": ownership,
                    "execution_intent_id": lineage.get("execution_intent_id"),
                    "broker_discovered": synthetic,
                    "management_mode": "ADVISORY" if synthetic else "PLATFORM_MANAGED",
                    "automation_mode": "ADVISORY" if synthetic else "FULLY_AUTOMATIC",
                    "dynamic_management": dict(lineage.get("dynamic_management") or {}),
                    "sector": "UNCLASSIFIED",
                    "m74_6_lineage_recovery": None if synthetic else {"source":lineage.get("recovery_source") or lineage.get("identity_match"),"recovered_at":now()},
                },
                created_by=actor,
                created_at=now(),
                updated_at=now(),
            )
            session.add(managed)
        else:
            meta = dict(managed.metadata_json or {})
            contract_ids = set(int(x) for x in (meta.get("broker_contract_ids") or []) if str(x).isdigit())
            contract_ids.add(int(row.contract_id))
            managed.state = "OPEN" if row.active else "CLOSED"
            managed.closed_at = row.closed_at
            managed.mark_json = mark.__dict__
            managed.health_json = health.to_dict()
            managed.decision_json = decision.to_dict()
            managed.updated_at = now()
            managed.version += 1
            if not synthetic:
                managed.trade_plan_id = str(lineage.get("trade_plan_id") or managed.trade_plan_id)
                managed.opportunity_id = str(lineage.get("opportunity_id") or managed.opportunity_id)
                managed.intelligence_id = lineage.get("intelligence_id") or managed.intelligence_id
                managed.strategy = str(lineage.get("strategy") or managed.strategy)
                managed.direction = str(lineage.get("direction") or managed.direction)
                managed.execution_id = lineage.get("execution_intent_id") or managed.execution_id
            managed.metadata_json = {
                **meta,
                "broker_contract_id": str(row.contract_id),
                "broker_contract_ids": sorted(contract_ids),
                "broker_leg_ratios": {**dict(meta.get("broker_leg_ratios") or {}), **dict(lineage.get("broker_leg_ratios") or {})},
                "broker_account_id": row.broker_account_id,
                "local_symbol": row.local_symbol,
                "provenance": row.provenance,
                "reconciliation_status": row.reconciliation_status,
                "m62_lineage": lineage or meta.get("m62_lineage", {}),
                "execution_intent_id": lineage.get("execution_intent_id") or meta.get("execution_intent_id"),
                "last_broker_sync": row.last_seen_at,
                "broker_discovered": synthetic if row.provenance != "INSTITUTIONAL_OPTIONS" else False,
                "management_mode": "ADVISORY" if synthetic else "PLATFORM_MANAGED",
                "automation_mode": "ADVISORY" if synthetic else "FULLY_AUTOMATIC",
                "dynamic_management": dict(lineage.get("dynamic_management") or meta.get("dynamic_management") or {}),
                "m74_6_lineage_recovery": meta.get("m74_6_lineage_recovery") if synthetic else (meta.get("m74_6_lineage_recovery") or {"source":lineage.get("recovery_source") or lineage.get("identity_match"),"recovered_at":now()}),
            }
        return managed

    @staticmethod
    def _retire_superseded_managed_projection(
        session: Session,
        superseded_position_id: str,
        canonical_position_id: str,
        row: BrokerCurrentPositionModel,
        actor: str,
    ) -> None:
        if superseded_position_id == canonical_position_id:
            return
        superseded = session.get(ManagedPositionModel, superseded_position_id)
        if superseded is None:
            return
        meta = dict(superseded.metadata_json or {})
        # Only auto-retire a broker-discovered/synthetic projection. Never silently
        # retire another platform-managed institutional position.
        synthetic = bool(meta.get("broker_discovered")) or str(superseded.trade_plan_id or "").startswith("BROKER-DISCOVERED:")
        if not synthetic:
            return
        superseded.state = "SUPERSEDED"
        superseded.closed_at = row.last_seen_at or now()
        superseded.version += 1
        superseded.updated_at = now()
        superseded.metadata_json = {
            **meta,
            "superseded_by_managed_position_id": canonical_position_id,
            "superseded_reason": "M74_6_1_INSTITUTIONAL_POSITION_PROMOTION",
            "superseded_actor": actor,
            "broker_contract_id": str(row.contract_id),
        }

        # Keep the historical manager row, but make it non-active so UI and
        # autonomous cycles cannot continue managing the duplicate projection.
        try:
            from trading_ai.autonomous_position_management.models import M73PositionManagerModel
            manager = session.scalar(
                select(M73PositionManagerModel).where(
                    M73PositionManagerModel.position_id == superseded_position_id
                )
            )
            if manager is not None:
                manager.state = "SUPERSEDED"
                manager.recovered_at = now()
                manager.metadata_json = {
                    **dict(manager.metadata_json or {}),
                    "superseded_by_managed_position_id": canonical_position_id,
                    "superseded_reason": "M74_6_1_INSTITUTIONAL_POSITION_PROMOTION",
                }

            from trading_ai.position_management.database_models import PositionExitInstructionModel
            for instruction in session.scalars(
                select(PositionExitInstructionModel).where(
                    PositionExitInstructionModel.position_id == superseded_position_id,
                    PositionExitInstructionModel.status.notin_(["FILLED", "CANCELLED", "CANCELED", "REJECTED", "FAILED", "SUPERSEDED", "COMPLETED"]),
                )
            ).all():
                instruction.status = "SUPERSEDED"
                instruction.payload = {
                    **dict(instruction.payload or {}),
                    "superseded_by_managed_position_id": canonical_position_id,
                    "superseded_reason": "M74_6_1_INSTITUTIONAL_POSITION_PROMOTION",
                    "superseded_at": now(),
                }
        except Exception:
            # Position convergence is authoritative; manager projection cleanup must
            # not prevent broker truth from being committed.
            pass

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

    @staticmethod
    def _resolve_alert(
        session: Session,
        portfolio_id: str,
        row: BrokerCurrentPositionModel,
        alert_type: str,
        *,
        reason: str,
    ) -> None:
        alerts = list(
            session.scalars(
                select(BrokerPortfolioAlertModel).where(
                    BrokerPortfolioAlertModel.portfolio_id == portfolio_id,
                    BrokerPortfolioAlertModel.broker_position_id == row.broker_position_id,
                    BrokerPortfolioAlertModel.alert_type == alert_type,
                    BrokerPortfolioAlertModel.status == "OPEN",
                )
            ).all()
        )
        for alert in alerts:
            alert.status = "RESOLVED"
            alert.resolved_at = now()
            alert.payload_json = {
                **dict(alert.payload_json or {}),
                "resolved_reason": reason,
                "resolved_managed_position_id": row.managed_position_id,
                "resolved_provenance": row.provenance,
            }
