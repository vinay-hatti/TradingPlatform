from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import text

from trading_ai.database.session import SessionLocal


def _date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _business_day_age(start: date, end: date) -> int:
    """Count weekdays after start through end; weekends do not make snapshots stale."""
    if end <= start:
        return 0
    days = 0
    cursor = start
    while cursor < end:
        cursor = date.fromordinal(cursor.toordinal() + 1)
        if cursor.weekday() < 5:
            days += 1
    return days


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

    def latest(
        self,
        symbol: str,
        horizon_days: int = 10,
        reference_date: date | datetime | str | None = None,
    ) -> dict[str, Any] | None:
        """Return the nearest governed forecast horizon from the latest eligible date.

        Forecast model horizons are discrete (currently 5/10/20). Scanner candidates
        may carry arbitrary option DTE values. Exact matching caused valid forecasts to
        be reported as MISSING for candidates such as 2-DTE and 63-DTE index options.
        """
        requested_horizon = max(1, int(horizon_days or 10))
        effective_reference_date = _date(reference_date or date.today())

        with self.session_factory() as session:
            row = session.execute(
                text(
                    """
                    WITH latest_eligible_date AS (
                        SELECT MAX(as_of_date) AS as_of_date
                        FROM stock_trend_forecast_snapshot
                        WHERE symbol = :symbol
                          AND as_of_date <= :reference_date
                          AND status = 'READY'
                    )
                    SELECT
                        snapshot.payload_json,
                        snapshot.horizon_days,
                        snapshot.as_of_date
                    FROM stock_trend_forecast_snapshot snapshot
                    JOIN latest_eligible_date latest
                      ON latest.as_of_date = snapshot.as_of_date
                    WHERE snapshot.symbol = :symbol
                      AND snapshot.status = 'READY'
                    ORDER BY
                        ABS(snapshot.horizon_days - :requested_horizon),
                        snapshot.horizon_days ASC,
                        snapshot.snapshot_timestamp DESC
                    LIMIT 1
                    """
                ),
                {
                    "symbol": str(symbol).upper(),
                    "reference_date": effective_reference_date,
                    "requested_horizon": requested_horizon,
                },
            ).mappings().one_or_none()

        if not row:
            return None

        value = row["payload_json"]
        payload = value if isinstance(value, dict) else json.loads(value)
        payload = dict(payload)
        resolved_horizon = int(row["horizon_days"])
        payload["forecast_requested_horizon_days"] = requested_horizon
        payload["forecast_resolved_horizon_days"] = resolved_horizon
        payload["forecast_horizon_distance_days"] = abs(
            resolved_horizon - requested_horizon
        )
        payload["forecast_horizon_resolution"] = (
            "EXACT"
            if resolved_horizon == requested_horizon
            else "NEAREST_AVAILABLE"
        )
        return payload

    def scanner_context(
        self,
        symbol: str,
        signal: str,
        horizon_days: int = 10,
        maximum_age_days: int = 3,
        reference_date=None,
    ):
        requested_horizon = max(1, int(horizon_days or 10))
        neutral = {
            "forecast_context_status": "MISSING",
            "forecast_score_adjustment": 0.0,
            "forecast_direction": "UNAVAILABLE",
            "forecast_horizon_days": requested_horizon,
            "forecast_requested_horizon_days": requested_horizon,
            "forecast_resolved_horizon_days": None,
            "forecast_horizon_distance_days": None,
            "forecast_horizon_resolution": "UNRESOLVED",
            "continuation_probability": 50.0,
            "reversal_probability": 50.0,
            "forecast_confidence_score": 0.0,
            "forecast_context_warning": "No persisted READY trend forecast snapshot.",
        }

        effective_reference_date = _date(reference_date or date.today())
        payload = self.latest(
            symbol,
            requested_horizon,
            reference_date=effective_reference_date,
        )
        if not payload:
            return neutral

        age = _business_day_age(
            _date(payload["as_of_date"]),
            effective_reference_date,
        )
        resolved_horizon = int(
            payload.get("forecast_resolved_horizon_days", payload["horizon_days"])
        )
        horizon_resolution = payload.get(
            "forecast_horizon_resolution",
            "EXACT" if resolved_horizon == requested_horizon else "NEAREST_AVAILABLE",
        )

        if age > maximum_age_days:
            neutral.update(
                forecast_context_status="STALE",
                forecast_snapshot_date=payload["as_of_date"],
                forecast_snapshot_age_days=age,
                forecast_resolved_horizon_days=resolved_horizon,
                forecast_horizon_days=resolved_horizon,
                forecast_horizon_distance_days=abs(
                    resolved_horizon - requested_horizon
                ),
                forecast_horizon_resolution=horizon_resolution,
                forecast_context_warning=(
                    "Forecast snapshot exceeds governed maximum business-day age."
                ),
            )
            return neutral

        context_status = (
            "FRESH"
            if horizon_resolution == "EXACT"
            else "FRESH_APPROXIMATE_HORIZON"
        )
        warning = ""
        if horizon_resolution != "EXACT":
            warning = (
                f"Requested {requested_horizon}D forecast; resolved to nearest "
                f"available {resolved_horizon}D governed horizon."
            )

        neutral.update(
            forecast_context_status=context_status,
            forecast_snapshot_date=payload["as_of_date"],
            forecast_snapshot_age_days=age,
            forecast_horizon_days=resolved_horizon,
            forecast_requested_horizon_days=requested_horizon,
            forecast_resolved_horizon_days=resolved_horizon,
            forecast_horizon_distance_days=abs(
                resolved_horizon - requested_horizon
            ),
            forecast_horizon_resolution=horizon_resolution,
            forecast_direction=payload["forecast_direction"],
            continuation_probability=float(payload["continuation_probability"]),
            reversal_probability=float(payload["reversal_probability"]),
            forecast_confidence_score=float(payload["confidence_score"]),
            forecast_confidence_grade=payload["confidence_grade"],
            forecast_expected_return_pct=float(payload["expected_return_pct"]),
            forecast_expected_volatility_pct=float(
                payload["expected_volatility_pct"]
            ),
            forecast_persistence_days=int(payload["persistence_days_estimate"]),
            forecast_score_adjustment=float(
                payload.get("signal_adjustment", {}).get(
                    str(signal).upper(), 0.0
                )
            ),
            forecast_context_warning=warning,
        )
        return neutral
