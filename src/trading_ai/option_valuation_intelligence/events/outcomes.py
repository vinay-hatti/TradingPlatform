from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text


def _event_date_sql(alias: str = "event_date") -> str:
    return (
        f"CASE WHEN {alias} ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}' "
        f"THEN SUBSTRING({alias} FROM 1 FOR 10)::date ELSE NULL END"
    )


def _date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct(end: float | None, start: float | None) -> float | None:
    if end is None or start is None or start <= 0:
        return None
    return (end / start - 1.0) * 100.0


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EventOutcomePolicy:
    maximum_days_past: int = 3650
    minimum_days_after_event: int = 1
    forecast_snapshot_lookback_days: int = 14


class EventForecastSnapshotService:
    """Capture immutable daily pre-event evidence used by later learning."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def capture(self, *, as_of_date: date | None = None, horizon_days: int = 180, limit: int | None = None) -> dict[str, Any]:
        today = as_of_date or date.today()
        now = datetime.now(timezone.utc)
        event_date_expr = _event_date_sql()
        sql = f"""
            SELECT *
            FROM institutional_option_valuation_events
            WHERE status = 'ACTIVE'
              AND {event_date_expr} BETWEEN :today AND :horizon
            ORDER BY {event_date_expr}, event_id
        """
        if limit:
            sql += " LIMIT :limit"
        created = existing = skipped = 0
        with self.session_factory() as session:
            rows = session.execute(
                text(sql),
                {"today": today, "horizon": today + timedelta(days=horizon_days), "limit": limit},
            ).mappings().all()
            for event in rows:
                event_date = _date(event["event_date"])
                feature = {
                    "event_id": event["event_id"],
                    "symbol": event["symbol"],
                    "event_type": event["event_type"],
                    "event_date": event_date.isoformat(),
                    "event_session": event.get("event_session"),
                    "calendar_source": event.get("calendar_source") or event.get("source"),
                    "date_status": event.get("date_status"),
                    "event_time_status": event.get("event_time_status"),
                    "implied_move_pct": _float(event.get("implied_move_pct")),
                    "historical_move_pct": _float(event.get("historical_move_pct")),
                    "forecast_move_pct": _float(event.get("forecast_move_pct")),
                    "expected_move_pct": _float(event.get("expected_move_pct")),
                    "confidence": _float(event.get("confidence")) or 0.0,
                    "calculation_method": event.get("calculation_method") or "UNKNOWN",
                    "options_snapshot_id": event.get("options_snapshot_id"),
                    "evidence": event.get("evidence_json") or {},
                }
                if not any(feature[key] is not None for key in ("implied_move_pct", "historical_move_pct", "forecast_move_pct", "expected_move_pct")):
                    skipped += 1
                    continue
                snapshot_id = f"m696-forecast-{event['event_id']}-{today.isoformat()}"
                result = session.execute(
                    text("""
                        INSERT INTO institutional_event_forecast_snapshots
                        (forecast_snapshot_id,event_id,symbol,event_type,event_date,event_session,
                         snapshot_date,snapshot_timestamp,days_to_event,implied_move_pct,
                         historical_move_pct,forecast_move_pct,expected_move_pct,confidence,
                         calculation_method,feature_hash,feature_json,created_at)
                        VALUES
                        (:id,:event_id,:symbol,:event_type,:event_date,:event_session,
                         :snapshot_date,:snapshot_timestamp,:days_to_event,:implied,
                         :historical,:forecast,:expected,:confidence,:method,:feature_hash,
                         CAST(:feature_json AS jsonb),:created_at)
                        ON CONFLICT (event_id,snapshot_date) DO NOTHING
                    """),
                    {
                        "id": snapshot_id,
                        "event_id": event["event_id"],
                        "symbol": event["symbol"],
                        "event_type": event["event_type"],
                        "event_date": event_date,
                        "event_session": event.get("event_session"),
                        "snapshot_date": today,
                        "snapshot_timestamp": now,
                        "days_to_event": max(0, (event_date - today).days),
                        "implied": feature["implied_move_pct"],
                        "historical": feature["historical_move_pct"],
                        "forecast": feature["forecast_move_pct"],
                        "expected": feature["expected_move_pct"],
                        "confidence": feature["confidence"],
                        "method": feature["calculation_method"],
                        "feature_hash": _hash(feature),
                        "feature_json": _canonical_json(feature),
                        "created_at": now,
                    },
                )
                if result.rowcount:
                    created += 1
                else:
                    existing += 1
            session.commit()
        return {
            "status": "READY",
            "events_considered": len(rows),
            "created": created,
            "existing": existing,
            "skipped_without_forecast_evidence": skipped,
            "snapshot_date": today.isoformat(),
        }


class EventOutcomeRealizationService:
    """Realize completed events against canonical price_history and freeze outcomes."""

    def __init__(self, session_factory, policy: EventOutcomePolicy | None = None):
        self.session_factory = session_factory
        self.policy = policy or EventOutcomePolicy()

    def _bars(self, session, symbol: str, event_date: date) -> list[dict[str, Any]]:
        return session.execute(
            text("""
                SELECT date, open, high, low, close
                FROM price_history
                WHERE UPPER(symbol) = UPPER(:symbol)
                  AND date BETWEEN :start AND :end
                ORDER BY date
            """),
            {"symbol": symbol, "start": event_date - timedelta(days=8), "end": event_date + timedelta(days=8)},
        ).mappings().all()

    def _latest_pre_event_snapshot(self, session, event_id: str, event_date: date, event_session: str | None):
        cutoff = event_date if str(event_session or "").upper() == "POST_MARKET" else event_date - timedelta(days=1)
        return session.execute(
            text("""
                SELECT *
                FROM institutional_event_forecast_snapshots
                WHERE event_id = :event_id
                  AND snapshot_date <= :cutoff
                ORDER BY snapshot_date DESC, snapshot_timestamp DESC
                LIMIT 1
            """),
            {"event_id": event_id, "cutoff": cutoff},
        ).mappings().one_or_none()

    def realize(self, *, as_of_date: date | None = None, limit: int | None = None) -> dict[str, Any]:
        today = as_of_date or date.today()
        now = datetime.now(timezone.utc)
        event_date_expr = _event_date_sql()
        sql = f"""
            SELECT *
            FROM institutional_option_valuation_events
            WHERE {event_date_expr} < :today
              AND {event_date_expr} >= :oldest
              AND status IN ('ACTIVE','COMPLETED','SUPERSEDED')
            ORDER BY {event_date_expr}, event_id
        """
        if limit:
            sql += " LIMIT :limit"
        created = updated = finalized = provisional = insufficient = 0
        with self.session_factory() as session:
            events = session.execute(
                text(sql),
                {"today": today, "oldest": today - timedelta(days=self.policy.maximum_days_past), "limit": limit},
            ).mappings().all()
            for event in events:
                event_date = _date(event["event_date"])
                symbol = "SPY" if str(event["symbol"]).upper() in ("*", "ALL") else str(event["symbol"]).upper()
                bars = self._bars(session, symbol, event_date)
                prior = [row for row in bars if row["date"] < event_date]
                event_day = next((row for row in bars if row["date"] == event_date), None)
                after = [row for row in bars if row["date"] > event_date]
                session_name = str(event.get("event_session") or "UNKNOWN").upper()
                pre_close = _float(prior[-1]["close"]) if prior else None
                event_open = _float(event_day["open"]) if event_day else None
                event_close = _float(event_day["close"]) if event_day else None
                next_open = _float(after[0]["open"]) if after else None
                next_close = _float(after[0]["close"]) if after else None

                if session_name == "POST_MARKET":
                    base = event_close or pre_close
                    gap = _pct(next_open, base)
                    close_to_close = _pct(next_close, base)
                    directional = close_to_close
                else:
                    base = pre_close
                    gap = _pct(event_open, base)
                    close_to_close = _pct(event_close, base)
                    directional = close_to_close
                next_close_move = _pct(next_close, pre_close)
                candidates = [abs(v) for v in (gap, close_to_close, next_close_move) if v is not None]
                realized = max(candidates) if candidates else None
                is_final = realized is not None and bool(after if session_name == "POST_MARKET" else event_day)
                status = "FINAL" if is_final else "PROVISIONAL"
                if realized is None:
                    insufficient += 1
                snapshot = self._latest_pre_event_snapshot(session, event["event_id"], event_date, session_name)
                predicted = _float(snapshot.get("expected_move_pct")) if snapshot else _float(event.get("expected_move_pct"))
                error = realized - predicted if realized is not None and predicted is not None else None
                payload = {
                    "source": "price_history",
                    "symbol_proxy": symbol,
                    "event_session": session_name,
                    "bars_found": len(bars),
                    "pre_event_snapshot": snapshot["forecast_snapshot_id"] if snapshot else None,
                    "calculation": {
                        "gap_move_pct": gap,
                        "close_to_close_move_pct": close_to_close,
                        "next_close_move_pct": next_close_move,
                        "realized_absolute_move_pct": realized,
                    },
                }
                outcome_id = f"m696-outcome-{event['event_id']}"
                existing = session.execute(
                    text("SELECT status FROM institutional_event_outcomes WHERE event_id=:event_id"),
                    {"event_id": event["event_id"]},
                ).scalar()
                session.execute(
                    text("""
                        INSERT INTO institutional_event_outcomes
                        (outcome_id,event_id,observed_at,predicted_move_pct,realized_move_pct,
                         forecast_error_pct,payload_json,symbol,event_type,event_date,event_session,
                         status,forecast_snapshot_id,pre_event_close,event_open,event_close,
                         next_session_open,next_session_close,gap_move_pct,close_to_close_move_pct,
                         next_close_move_pct,realized_absolute_move_pct,prediction_error_pct,
                         directional_move_pct,finalized_at)
                        VALUES
                        (:outcome_id,:event_id,:observed_at,:predicted,:realized,:error,
                         CAST(:payload AS jsonb),:symbol,:event_type,:event_date,:event_session,
                         :status,:snapshot_id,:pre_close,:event_open,:event_close,:next_open,
                         :next_close,:gap,:close_to_close,:next_close_move,:realized,:error,
                         :directional,:finalized_at)
                        ON CONFLICT (event_id) DO UPDATE SET
                          observed_at=EXCLUDED.observed_at,
                          predicted_move_pct=COALESCE(institutional_event_outcomes.predicted_move_pct,EXCLUDED.predicted_move_pct),
                          realized_move_pct=EXCLUDED.realized_move_pct,
                          forecast_error_pct=EXCLUDED.forecast_error_pct,
                          payload_json=EXCLUDED.payload_json,
                          status=EXCLUDED.status,
                          forecast_snapshot_id=COALESCE(institutional_event_outcomes.forecast_snapshot_id,EXCLUDED.forecast_snapshot_id),
                          pre_event_close=EXCLUDED.pre_event_close,event_open=EXCLUDED.event_open,
                          event_close=EXCLUDED.event_close,next_session_open=EXCLUDED.next_session_open,
                          next_session_close=EXCLUDED.next_session_close,gap_move_pct=EXCLUDED.gap_move_pct,
                          close_to_close_move_pct=EXCLUDED.close_to_close_move_pct,
                          next_close_move_pct=EXCLUDED.next_close_move_pct,
                          realized_absolute_move_pct=EXCLUDED.realized_absolute_move_pct,
                          prediction_error_pct=EXCLUDED.prediction_error_pct,
                          directional_move_pct=EXCLUDED.directional_move_pct,
                          finalized_at=EXCLUDED.finalized_at
                    """),
                    {
                        "outcome_id": outcome_id,
                        "event_id": event["event_id"],
                        "observed_at": now.isoformat(),
                        "predicted": predicted,
                        "realized": realized,
                        "error": error,
                        "payload": _canonical_json(payload),
                        "symbol": str(event["symbol"]).upper(),
                        "event_type": event["event_type"],
                        "event_date": event_date,
                        "event_session": session_name,
                        "status": status,
                        "snapshot_id": snapshot["forecast_snapshot_id"] if snapshot else None,
                        "pre_close": pre_close,
                        "event_open": event_open,
                        "event_close": event_close,
                        "next_open": next_open,
                        "next_close": next_close,
                        "gap": gap,
                        "close_to_close": close_to_close,
                        "next_close_move": next_close_move,
                        "directional": directional,
                        "finalized_at": now if is_final else None,
                    },
                )
                if existing is None:
                    created += 1
                else:
                    updated += 1
                if is_final:
                    finalized += 1
                else:
                    provisional += 1
            session.commit()
        return {
            "status": "READY" if insufficient == 0 else "DEGRADED",
            "events_considered": len(events),
            "created": created,
            "updated": updated,
            "finalized": finalized,
            "provisional": provisional,
            "insufficient_price_history": insufficient,
            "completed_at": now.isoformat(),
        }
