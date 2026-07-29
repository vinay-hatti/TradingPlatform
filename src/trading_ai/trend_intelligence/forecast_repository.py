from __future__ import annotations
import json
from datetime import date, datetime
from sqlalchemy import text
from trading_ai.database.session import SessionLocal

def _date(value):
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    return date.fromisoformat(str(value)[:10])

class TrendForecastRepository:
    def __init__(self, session_factory=SessionLocal): self.session_factory = session_factory
    def save(self, snapshot) -> None:
        payload = snapshot.to_dict() if hasattr(snapshot, "to_dict") else dict(snapshot)
        with self.session_factory() as session:
            session.execute(text("""INSERT INTO stock_trend_forecast_snapshot
            (symbol, as_of_date, snapshot_timestamp, horizon_days, status, payload_json)
            VALUES (:symbol,:as_of_date,:snapshot_timestamp,:horizon_days,:status,CAST(:payload AS jsonb))"""),
            {"symbol": payload["symbol"], "as_of_date": payload["as_of_date"], "snapshot_timestamp": payload["snapshot_timestamp"],
             "horizon_days": payload["horizon_days"], "status": payload.get("status","READY"), "payload": json.dumps(payload)})
            session.commit()
    def latest(self, symbol: str, horizon_days: int = 10):
        with self.session_factory() as session:
            value = session.execute(text("""SELECT payload_json FROM stock_trend_forecast_snapshot
            WHERE symbol=:symbol AND horizon_days=:h ORDER BY snapshot_timestamp DESC LIMIT 1"""),
            {"symbol": symbol.upper(), "h": horizon_days}).scalar_one_or_none()
        return value if isinstance(value, dict) else json.loads(value) if value else None
    def scanner_context(self, symbol: str, signal: str, horizon_days: int = 10, maximum_age_days: int = 3, reference_date=None):
        neutral={"forecast_context_status":"MISSING","forecast_score_adjustment":0.0,"forecast_direction":"UNAVAILABLE",
        "forecast_horizon_days":horizon_days,"continuation_probability":50.0,"reversal_probability":50.0,"forecast_confidence_score":0.0,
        "forecast_context_warning":"No persisted trend forecast snapshot."}
        payload=self.latest(symbol,horizon_days)
        if not payload:return neutral
        age=max(0,(_date(reference_date or date.today())-_date(payload["as_of_date"])).days)
        if age>maximum_age_days:
            neutral.update(forecast_context_status="STALE",forecast_snapshot_age_days=age,forecast_context_warning="Forecast snapshot exceeds governed maximum age.")
            return neutral
        neutral.update(forecast_context_status="FRESH",forecast_snapshot_date=payload["as_of_date"],forecast_snapshot_age_days=age,
        forecast_direction=payload["forecast_direction"],continuation_probability=float(payload["continuation_probability"]),
        reversal_probability=float(payload["reversal_probability"]),forecast_confidence_score=float(payload["confidence_score"]),
        forecast_confidence_grade=payload["confidence_grade"],forecast_expected_return_pct=float(payload["expected_return_pct"]),
        forecast_expected_volatility_pct=float(payload["expected_volatility_pct"]),forecast_persistence_days=int(payload["persistence_days_estimate"]),
        forecast_score_adjustment=float(payload.get("signal_adjustment",{}).get(str(signal).upper(),0.0)),forecast_context_warning="")
        return neutral
