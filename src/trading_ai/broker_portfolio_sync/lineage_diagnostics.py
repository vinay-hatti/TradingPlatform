from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.autonomous_position_management.models import M73PositionManagerModel
from trading_ai.broker.ibkr.database_models import BrokerOrderModel
from trading_ai.execution_workspace.models import ExecutionIntentModel
from trading_ai.portfolio_intelligence.models import ManagedPositionModel
from trading_ai.position_management.database_models import PositionExitInstructionModel

from .models import BrokerCurrentPositionModel
from .service import BrokerPortfolioSynchronizationService

TERMINAL_INSTRUCTIONS = {"FILLED", "CANCELLED", "CANCELED", "REJECTED", "FAILED", "SUPERSEDED", "COMPLETED"}
PROTECTIVE_LABELS = {"STRUCTURAL_STOP", "EMERGENCY_OPTION_STOP"}


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _hours(a: str | None, b: str | None) -> float | None:
    aa, bb = _dt(a), _dt(b)
    if aa is None or bb is None:
        return None
    return abs((aa - bb).total_seconds()) / 3600.0


def _upper(value: Any) -> str:
    return str(value or "").strip().upper()


@dataclass(frozen=True)
class MatchEvidence:
    complete_leg_set: bool
    side_match: bool
    proportional_quantity_match: bool
    matched_contract_ids: tuple[int, ...]
    expected_leg_count: int
    matched_leg_count: int
    quantity_multiplier: float | None


class LineageDiagnosticsService:
    """Read-only explanation engine for broker-position lineage recovery.

    M74.7 deliberately does not promote or mutate broker-discovered positions.  It
    explains why the existing recovery engine can or cannot safely establish
    institutional lineage, using the exact broker legs and immutable trade-plan
    contracts already persisted by the platform.
    """

    VERSION = "M74.7-LINEAGE-DIAGNOSTICS-1.0"

    def __init__(self, session: Session):
        self.s = session

    @staticmethod
    def _match_plan_to_broker_rows(plan: TradePlanModel, broker_rows: list[BrokerCurrentPositionModel]) -> MatchEvidence:
        legs = [x for x in list(plan.legs_json or []) if isinstance(x, dict)]
        used: set[int] = set()
        matched: list[tuple[dict, BrokerCurrentPositionModel]] = []
        for leg in legs:
            found = None
            for row in broker_rows:
                if int(row.contract_id) in used:
                    continue
                if BrokerPortfolioSynchronizationService._trade_plan_broker_identity_match(plan, row) is None:
                    continue
                # Ensure this row matches this specific leg, not merely another plan leg.
                fake_plan = type("_Plan", (), {"legs_json": [leg], "symbol": plan.symbol})()
                if BrokerPortfolioSynchronizationService._trade_plan_broker_identity_match(fake_plan, row) is None:
                    continue
                found = row
                break
            if found is not None:
                used.add(int(found.contract_id))
                matched.append((leg, found))

        complete = bool(legs) and len(matched) == len(legs)
        side_match = complete
        multipliers: list[float] = []
        if complete:
            for leg, row in matched:
                side = _upper(leg.get("side"))
                qty = max(1.0, float(leg.get("quantity") or 1.0))
                signed = float(row.signed_quantity or 0.0)
                if (side == "BUY" and signed <= 0) or (side == "SELL" and signed >= 0):
                    side_match = False
                multipliers.append(abs(signed) / qty)
        qty_match = bool(multipliers) and max(multipliers) - min(multipliers) < 1e-9 and min(multipliers) > 0
        multiplier = multipliers[0] if qty_match else None
        return MatchEvidence(
            complete_leg_set=complete,
            side_match=side_match,
            proportional_quantity_match=qty_match,
            matched_contract_ids=tuple(sorted(int(row.contract_id) for _, row in matched)),
            expected_leg_count=len(legs),
            matched_leg_count=len(matched),
            quantity_multiplier=multiplier,
        )

    def _broker_order_for_intent(self, intent: ExecutionIntentModel) -> BrokerOrderModel | None:
        rows = list(self.s.scalars(select(BrokerOrderModel).where(
            BrokerOrderModel.portfolio_id == intent.portfolio_id,
            BrokerOrderModel.symbol == intent.symbol,
        )).all())
        token = intent.execution_intent_id
        for row in rows:
            if token in str(row.aggregate_id or "") or token in str(row.client_order_id or ""):
                return row
            raw = dict(row.raw_json or {})
            req = dict(raw.get("request") or {})
            meta = dict(req.get("metadata") or {})
            if str(meta.get("execution_intent_id") or "") == token:
                return row
        return None

    def _score_candidate(self, intent: ExecutionIntentModel, plan: TradePlanModel | None, broker_rows: list[BrokerCurrentPositionModel]) -> dict:
        evidence = self._match_plan_to_broker_rows(plan, broker_rows) if plan else MatchEvidence(False, False, False, (), 0, 0, None)
        score = 0
        reasons: list[str] = []
        score += 10; reasons.append("SAME_SYMBOL")
        if intent.portfolio_id == broker_rows[0].portfolio_id:
            score += 10; reasons.append("SAME_PORTFOLIO")
        if plan is not None:
            score += 5; reasons.append("TRADE_PLAN_FOUND")
        if evidence.complete_leg_set:
            score += 35; reasons.append("COMPLETE_EXACT_LEG_SET")
        elif evidence.matched_leg_count:
            reasons.append(f"PARTIAL_LEG_SET:{evidence.matched_leg_count}/{evidence.expected_leg_count}")
        else:
            reasons.append("NO_EXACT_LEG_MATCH")
        if evidence.side_match:
            score += 10; reasons.append("BUY_SELL_DIRECTION_MATCH")
        elif evidence.complete_leg_set:
            reasons.append("BUY_SELL_DIRECTION_MISMATCH")
        if evidence.proportional_quantity_match:
            score += 10; reasons.append(f"PROPORTIONAL_QUANTITY_MATCH:x{evidence.quantity_multiplier:g}")
        elif evidence.complete_leg_set:
            reasons.append("QUANTITY_RATIO_MISMATCH")
        broker_order = self._broker_order_for_intent(intent)
        if broker_order is not None:
            score += 10; reasons.append(f"BROKER_ORDER_FOUND:{broker_order.status}")
        else:
            reasons.append("BROKER_ORDER_MISSING")
        age = _hours(broker_rows[0].first_seen_at, intent.created_at)
        if age is not None:
            if age <= 4:
                score += 10; reasons.append("TIME_PROXIMITY_LE_4H")
            elif age <= 24:
                score += 7; reasons.append("TIME_PROXIMITY_LE_24H")
            elif age <= 72:
                score += 3; reasons.append("TIME_PROXIMITY_LE_72H")
            else:
                reasons.append(f"TIME_DISTANCE_HOURS:{age:.1f}")
        state = _upper(intent.state)
        if state in {"APPROVED", "SUBMITTED", "ACKNOWLEDGED", "PARTIALLY_FILLED", "FILLED", "CANCEL_REQUESTED", "CANCELLED"}:
            score += 5; reasons.append(f"EXECUTION_STATE:{state}")
        else:
            reasons.append(f"EXECUTION_STATE_WEAK:{state}")
        return {
            "execution_intent_id": intent.execution_intent_id,
            "trade_plan_id": intent.trade_plan_id,
            "execution_state": intent.state,
            "strategy": intent.strategy,
            "score": min(100, score),
            "broker_order_id": broker_order.broker_order_id if broker_order else None,
            "broker_order_status": broker_order.status if broker_order else None,
            "evidence": {
                "complete_leg_set": evidence.complete_leg_set,
                "side_match": evidence.side_match,
                "proportional_quantity_match": evidence.proportional_quantity_match,
                "quantity_multiplier": evidence.quantity_multiplier,
                "expected_leg_count": evidence.expected_leg_count,
                "matched_leg_count": evidence.matched_leg_count,
                "matched_contract_ids": list(evidence.matched_contract_ids),
                "hours_from_intent_to_first_broker_seen": age,
            },
            "reasons": reasons,
        }

    def _management_health(self, managed: ManagedPositionModel | None) -> dict:
        if managed is None:
            return {"manager_state": None, "automation_mode": None, "protection_state": None, "active_exit_instructions": 0, "protective_rule_present": False, "protection_consistency": "NO_MANAGED_POSITION"}
        manager = self.s.scalar(select(M73PositionManagerModel).where(M73PositionManagerModel.position_id == managed.position_id))
        instructions = list(self.s.scalars(select(PositionExitInstructionModel).where(PositionExitInstructionModel.position_id == managed.position_id)).all())
        active = [x for x in instructions if _upper(x.status) not in TERMINAL_INSTRUCTIONS]
        protective = any(_upper((x.payload or {}).get("label")) in PROTECTIVE_LABELS for x in active)
        protection_state = manager.protection_state if manager else None
        if protective and _upper(protection_state) != "PLATFORM_PROTECTED":
            consistency = "STALE_PROTECTION_STATE"
        elif active and not protective:
            consistency = "NO_PROTECTIVE_RULE_ARMED"
        else:
            consistency = "CONSISTENT"
        return {
            "manager_state": manager.state if manager else None,
            "automation_mode": manager.automation_mode if manager else None,
            "protection_state": protection_state,
            "heartbeat_at": manager.heartbeat_at if manager else None,
            "active_exit_instructions": len(active),
            "protective_rule_present": protective,
            "protection_consistency": consistency,
        }

    def diagnose(self, portfolio_id: str = "PAPER-PRIMARY") -> dict:
        broker_rows = list(self.s.scalars(select(BrokerCurrentPositionModel).where(
            BrokerCurrentPositionModel.portfolio_id == portfolio_id,
            BrokerCurrentPositionModel.active.is_(True),
            BrokerCurrentPositionModel.signed_quantity != 0,
        )).all())
        by_symbol: dict[str, list[BrokerCurrentPositionModel]] = {}
        for row in broker_rows:
            by_symbol.setdefault(row.symbol, []).append(row)

        results: list[dict] = []
        processed_recovered: set[str] = set()
        for row in broker_rows:
            managed = self.s.get(ManagedPositionModel, row.managed_position_id) if row.managed_position_id else None
            broker_discovered = managed is None or bool((managed.metadata_json or {}).get("broker_discovered")) or str(managed.trade_plan_id or "").startswith("BROKER-DISCOVERED:")
            if not broker_discovered:
                if managed.position_id in processed_recovered:
                    continue
                processed_recovered.add(managed.position_id)
                group = [x for x in broker_rows if x.managed_position_id == managed.position_id]
                results.append({
                    "symbol": managed.symbol,
                    "contract_ids": sorted(int(x.contract_id) for x in group),
                    "managed_position_id": managed.position_id,
                    "current_classification": "RECOVERED_INSTITUTIONAL",
                    "recovery_classification": "RECOVERED",
                    "confidence": 100,
                    "best_candidate": {"execution_intent_id": managed.execution_id, "trade_plan_id": managed.trade_plan_id, "strategy": managed.strategy, "score": 100, "reasons": ["CANONICAL_INSTITUTIONAL_POSITION_ALREADY_ESTABLISHED"]},
                    "management": self._management_health(managed),
                })
                continue

            symbol_rows = by_symbol.get(row.symbol, [])
            intents = list(self.s.scalars(select(ExecutionIntentModel).where(
                ExecutionIntentModel.portfolio_id == portfolio_id,
                ExecutionIntentModel.symbol == row.symbol,
            ).order_by(ExecutionIntentModel.created_at.desc())).all())
            candidates = []
            for intent in intents:
                plan = self.s.get(TradePlanModel, intent.trade_plan_id)
                candidates.append(self._score_candidate(intent, plan, symbol_rows))
            candidates.sort(key=lambda x: (x["score"], x["execution_intent_id"]), reverse=True)
            best = candidates[0] if candidates else None
            second = candidates[1] if len(candidates) > 1 else None
            ambiguous = bool(best and second and best["score"] >= 70 and second["score"] >= 70 and abs(best["score"] - second["score"]) <= 5)
            if not best or best["score"] < 50:
                classification = "LIKELY_EXTERNAL"
            elif ambiguous:
                classification = "BLOCKED_REVIEW"
            elif best["score"] >= 85 and best["evidence"]["complete_leg_set"] and best["evidence"]["side_match"] and best["evidence"]["proportional_quantity_match"]:
                classification = "AUTO_RECOVERABLE"
            else:
                classification = "BLOCKED_REVIEW"
            blockers = []
            if not best:
                blockers.append("NO_EXECUTION_INTENT_CANDIDATE")
            else:
                ev = best["evidence"]
                if not ev["complete_leg_set"]: blockers.append("INCOMPLETE_LEG_SET")
                if ev["complete_leg_set"] and not ev["side_match"]: blockers.append("SIDE_MISMATCH")
                if ev["complete_leg_set"] and not ev["proportional_quantity_match"]: blockers.append("QUANTITY_RATIO_MISMATCH")
                if best["broker_order_id"] is None: blockers.append("BROKER_ORDER_LINEAGE_MISSING")
                if ambiguous: blockers.append("AMBIGUOUS_HIGH_CONFIDENCE_CANDIDATES")
            results.append({
                "symbol": row.symbol,
                "contract_ids": sorted(int(x.contract_id) for x in symbol_rows),
                "managed_position_id": row.managed_position_id,
                "current_classification": "BROKER_DISCOVERED",
                "recovery_classification": classification,
                "confidence": int(best["score"] if best else 0),
                "blockers": blockers,
                "best_candidate": best,
                "alternate_candidates": candidates[1:4],
                "management": self._management_health(managed),
            })
            # One diagnostic row per symbol/leg-set rather than one per broker leg.
            for other in symbol_rows:
                if other is not row:
                    # Mark via an ephemeral attribute used only in this loop.
                    setattr(other, "_m747_diagnosed", True)
        # Remove duplicate broker-discovered rows generated by the symbol loop.
        dedup: list[dict] = []
        seen_keys: set[tuple] = set()
        for item in results:
            key = (item["symbol"], tuple(item["contract_ids"]), item["recovery_classification"])
            if key in seen_keys:
                continue
            seen_keys.add(key); dedup.append(item)
        summary = {k: 0 for k in ["RECOVERED", "AUTO_RECOVERABLE", "BLOCKED_REVIEW", "LIKELY_EXTERNAL"]}
        for item in dedup:
            summary[item["recovery_classification"]] = summary.get(item["recovery_classification"], 0) + 1
        return {
            "version": self.VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "portfolio_id": portfolio_id,
            "summary": summary,
            "positions": dedup,
        }
