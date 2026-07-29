from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy import text

from trading_ai.database.session import SessionLocal


def _date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


class InstitutionalTrendRepository:
    def __init__(self, session_factory=SessionLocal) -> None:
        self.session_factory = session_factory

    def save(self, snapshot) -> None:
        payload = snapshot.to_dict() if hasattr(snapshot, "to_dict") else dict(snapshot)
        with self.session_factory() as session:
            session.execute(
                text(
                    """
                    INSERT INTO stock_institutional_trend_snapshot
                    (symbol, as_of_date, snapshot_timestamp, status, participation_score,
                     leadership_score, trend_quality_score, deterioration_risk_score, payload_json)
                    VALUES
                    (:symbol, :as_of_date, :snapshot_timestamp, :status, :participation_score,
                     :leadership_score, :trend_quality_score, :deterioration_risk_score,
                     CAST(:payload AS jsonb))
                    """
                ),
                {
                    "symbol": payload["symbol"],
                    "as_of_date": payload["as_of_date"],
                    "snapshot_timestamp": payload["snapshot_timestamp"],
                    "status": payload.get("status", "READY"),
                    "participation_score": payload["participation_score"],
                    "leadership_score": payload["leadership_score"],
                    "trend_quality_score": payload["trend_quality_score"],
                    "deterioration_risk_score": payload["deterioration_risk_score"],
                    "payload": json.dumps(payload),
                },
            )
            session.commit()

    def latest(self, symbol: str):
        with self.session_factory() as session:
            value = session.execute(
                text(
                    """
                    SELECT payload_json
                    FROM stock_institutional_trend_snapshot
                    WHERE symbol=:symbol
                    ORDER BY snapshot_timestamp DESC
                    LIMIT 1
                    """
                ),
                {"symbol": str(symbol).upper()},
            ).scalar_one_or_none()
        return value if isinstance(value, dict) else json.loads(value) if value else None

    def scanner_context(self, symbol: str, maximum_age_days: int = 3, reference_date=None):
        neutral = {
            "institutional_context_status": "MISSING",
            "participation_score": 50.0,
            "participation_grade": "UNAVAILABLE",
            "leadership_score": 50.0,
            "leadership_grade": "UNAVAILABLE",
            "trend_quality_score": 50.0,
            "institutional_conviction_score": 50.0,
            "deterioration_risk_score": 50.0,
            "institutional_context_warning": "No persisted institutional trend snapshot.",
        }
        payload = self.latest(symbol)
        if not payload:
            return neutral
        age = max(0, (_date(reference_date or date.today()) - _date(payload["as_of_date"])).days)
        if age > maximum_age_days:
            neutral.update(
                institutional_context_status="STALE",
                institutional_snapshot_age_days=age,
                institutional_context_warning="Institutional trend snapshot exceeds governed maximum age.",
            )
            return neutral
        neutral.update(
            institutional_context_status="FRESH",
            institutional_snapshot_date=payload["as_of_date"],
            institutional_snapshot_age_days=age,
            participation_score=float(payload["participation_score"]),
            participation_grade=payload["participation_grade"],
            leadership_score=float(payload["leadership_score"]),
            leadership_grade=payload["leadership_grade"],
            trend_quality_score=float(payload["trend_quality_score"]),
            institutional_conviction_score=float(payload["institutional_conviction_score"]),
            deterioration_risk_score=float(payload["deterioration_risk_score"]),
            participation_state=payload["participation_state"],
            leadership_state=payload["leadership_state"],
            deterioration_state=payload["deterioration_state"],
            breadth_confirmation_score=float(payload["breadth_confirmation_score"]),
            cross_asset_confirmation_score=float(payload["cross_asset_confirmation_score"]),
            institutional_context_warning="",
        )
        return neutral
