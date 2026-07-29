from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from sqlalchemy import text

from trading_ai.database.session import SessionLocal


def _date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _business_day_age(snapshot_date, reference_date) -> int:
    """Return elapsed weekday sessions after snapshot_date through reference_date.

    Same-day snapshots have age 0. Weekends are not counted. Exchange holidays are
    intentionally left to the upstream snapshot calendar; this prevents a Friday
    snapshot from becoming stale only because Saturday and Sunday elapsed.
    """
    start = _date(snapshot_date)
    end = _date(reference_date)
    if end <= start:
        return 0
    age = 0
    cursor = start + timedelta(days=1)
    while cursor <= end:
        if cursor.weekday() < 5:
            age += 1
        cursor += timedelta(days=1)
    return age


class TrendForecastRepository:
    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def save(self, snapshot) -> None:
        payload = snapshot.to_dict() if hasattr(snapshot, "to_dict") else dict(snapshot)
        with self.session_factory() as session:
            session.execute(
                text(
                    """INSERT INTO stock_trend_forecast_snapshot
                    (symbol, as_of_date, snapshot_timestamp, horizon_days, status, payload_json)
                    VALUES (:symbol,:as_of_date,:snapshot_timestamp,:horizon_days,:status,CAST(:payload AS jsonb))"""
                ),
                {
                    "symbol": payload["symbol"],
                    "as_of_date": payload["as_of_date"],
                    "snapshot_timestamp": payload["snapshot_timestamp"],
                    "horizon_days": payload["horizon_days"],
                    "status": payload.get("status", "READY"),
                    "payload": json.dumps(payload),
                },
            )
            session.commit()

    def latest(self, symbol: str, horizon_days: int = 10, reference_date=None):
        params = {"symbol": str(symbol).upper(), "h": int(horizon_days)}
        reference_clause = ""
        if reference_date is not None:
            params["reference_date"] = _date(reference_date)
            reference_clause = " AND as_of_date <= :reference_date"
        with self.session_factory() as session:
            row = session.execute(
                text(
                    f"""SELECT payload_json, as_of_date, snapshot_timestamp
                    FROM stock_trend_forecast_snapshot
                    WHERE symbol=:symbol AND horizon_days=:h{reference_clause}
                    ORDER BY as_of_date DESC, snapshot_timestamp DESC
                    LIMIT 1"""
                ),
                params,
            ).mappings().one_or_none()
        if not row:
            return None
        value = row["payload_json"]
        payload = value if isinstance(value, dict) else json.loads(value)
        payload = dict(payload)
        payload.setdefault("as_of_date", row["as_of_date"])
        payload.setdefault("snapshot_timestamp", row["snapshot_timestamp"])
        return payload

    def scanner_context(
        self,
        symbol: str,
        signal: str,
        horizon_days: int = 10,
        maximum_age_days: int = 3,
        reference_date=None,
    ):
        neutral = {
            "forecast_context_status": "MISSING",
            "forecast_score_adjustment": 0.0,
            "forecast_direction": "UNAVAILABLE",
            "forecast_horizon_days": horizon_days,
            "continuation_probability": 50.0,
            "reversal_probability": 50.0,
            "forecast_confidence_score": 0.0,
            "forecast_context_warning": "No persisted trend forecast snapshot.",
        }
        effective_reference_date = _date(reference_date or date.today())
        payload = self.latest(symbol, horizon_days, reference_date=effective_reference_date)
        if not payload:
            return neutral
        snapshot_date = _date(payload["as_of_date"])
        age = _business_day_age(snapshot_date, effective_reference_date)
        if age > maximum_age_days:
            neutral.update(
                forecast_context_status="STALE",
                forecast_snapshot_date=snapshot_date.isoformat(),
                forecast_snapshot_age_days=age,
                forecast_context_warning="Forecast snapshot exceeds governed maximum business-day age.",
            )
            return neutral
        neutral.update(
            forecast_context_status="FRESH",
            forecast_snapshot_date=snapshot_date.isoformat(),
            forecast_snapshot_age_days=age,
            forecast_direction=payload["forecast_direction"],
            continuation_probability=float(payload["continuation_probability"]),
            reversal_probability=float(payload["reversal_probability"]),
            forecast_confidence_score=float(payload["confidence_score"]),
            forecast_confidence_grade=payload["confidence_grade"],
            forecast_expected_return_pct=float(payload["expected_return_pct"]),
            forecast_expected_volatility_pct=float(payload["expected_volatility_pct"]),
            forecast_persistence_days=int(payload["persistence_days_estimate"]),
            forecast_score_adjustment=float(
                payload.get("signal_adjustment", {}).get(str(signal).upper(), 0.0)
            ),
            forecast_context_warning="",
        )
        return neutral
