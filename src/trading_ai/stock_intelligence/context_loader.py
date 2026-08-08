from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from sqlalchemy import text


def _payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _namespace(**values: Any) -> SimpleNamespace:
    return SimpleNamespace(**values)


class PersistedStockContextLoader:
    """Load the latest persisted cross-domain intelligence for Stock Scanner publication.

    The scanner does not recompute dealer, market, trend, or forecast analytics. It joins
    the latest persisted snapshots produced by market ingestion and Trend Intelligence.
    Missing optional domains remain explicitly unavailable and are surfaced as warnings.
    """

    def __init__(self, session) -> None:
        self.session = session
        self._market_context: dict[str, Any] | None = None

    def _one(self, sql: str, **params: Any):
        try:
            return self.session.execute(text(sql), params).mappings().one_or_none()
        except Exception:
            # Optional intelligence tables may not exist in partially upgraded environments.
            self.session.rollback()
            return None

    def market(self) -> SimpleNamespace | None:
        if self._market_context is None:
            row = self._one(
                """
                SELECT trend_regime, market_bias, breadth_regime, confidence_score,
                       snapshot_timestamp, payload_json
                  FROM market_overview_snapshot
                 ORDER BY snapshot_timestamp DESC
                 LIMIT 1
                """
            )
            self._market_context = dict(row) if row else {}
        if not self._market_context:
            return None
        regime = (
            self._market_context.get("trend_regime")
            or self._market_context.get("market_bias")
            or "UNAVAILABLE"
        )
        return _namespace(
            regime=str(regime).upper(),
            current_regime=str(regime).upper(),
            breadth_regime=str(self._market_context.get("breadth_regime") or "UNAVAILABLE").upper(),
            confidence_score=float(self._market_context.get("confidence_score") or 0.0),
            snapshot_timestamp=str(self._market_context.get("snapshot_timestamp") or ""),
        )

    def trend(self, symbol: str) -> SimpleNamespace | None:
        row = self._one(
            """
            SELECT payload_json, snapshot_timestamp
              FROM stock_trend_snapshot
             WHERE symbol=:symbol
             ORDER BY snapshot_timestamp DESC
             LIMIT 1
            """,
            symbol=symbol,
        )
        if not row:
            return None
        payload = _payload(row["payload_json"])
        return _namespace(
            short_term_trend=str((payload.get("short_term") or {}).get("state") or "UNAVAILABLE").upper(),
            intermediate_term_trend=str((payload.get("intermediate_term") or {}).get("state") or "UNAVAILABLE").upper(),
            long_term_trend=str((payload.get("long_term") or {}).get("state") or "UNAVAILABLE").upper(),
            direction=str((payload.get("short_term") or {}).get("state") or "UNAVAILABLE").upper(),
            relative_strength_vs_spy=float(payload.get("relative_strength_vs_spy") or 0.0),
            relative_strength_vs_sector=float(payload.get("relative_strength_vs_sector") or 0.0),
            relative_strength_grade=str(payload.get("relative_strength_grade") or "UNAVAILABLE").upper(),
            snapshot_timestamp=str(row["snapshot_timestamp"] or ""),
        )

    def dealer(self, symbol: str) -> SimpleNamespace | None:
        row = self._one(
            """
            SELECT positioning_label, gamma_regime, confidence_score, as_of_date,
                   gamma_flip, primary_call_wall, primary_put_wall
              FROM dealer_position_snapshot
             WHERE symbol=:symbol
             ORDER BY as_of_date DESC, quote_date DESC
             LIMIT 1
            """,
            symbol=symbol,
        )
        if not row:
            return None
        return _namespace(
            positioning_label=str(row["positioning_label"] or "UNAVAILABLE").upper(),
            gamma_regime=str(row["gamma_regime"] or "UNAVAILABLE").upper(),
            confidence_score=float(row["confidence_score"] or 0.0),
            gamma_flip=row["gamma_flip"],
            primary_call_wall=row["primary_call_wall"],
            primary_put_wall=row["primary_put_wall"],
            as_of_date=str(row["as_of_date"] or ""),
        )

    def forecast(self, symbol: str) -> SimpleNamespace | None:
        row = self._one(
            """
            SELECT payload_json, snapshot_timestamp, horizon_days
              FROM stock_trend_forecast_snapshot
             WHERE symbol=:symbol AND status='READY'
             ORDER BY as_of_date DESC,
                      ABS(horizon_days - 10),
                      snapshot_timestamp DESC
             LIMIT 1
            """,
            symbol=symbol,
        )
        if not row:
            return None
        payload = _payload(row["payload_json"])
        return _namespace(
            direction=str(payload.get("forecast_direction") or payload.get("direction") or "UNAVAILABLE").upper(),
            forecast_direction=str(payload.get("forecast_direction") or payload.get("direction") or "UNAVAILABLE").upper(),
            confidence_score=float(payload.get("forecast_confidence_score") or payload.get("confidence_score") or 0.0),
            horizon_days=int(row["horizon_days"] or 0),
            snapshot_timestamp=str(row["snapshot_timestamp"] or ""),
        )

    def for_symbol(self, symbol: str) -> dict[str, Any]:
        trend = self.trend(symbol)
        dealer = self.dealer(symbol)
        market = self.market()
        forecast = self.forecast(symbol)
        return {
            "trend": trend,
            "dealer": dealer,
            "market_regime": market,
            "forecast": forecast,
        }
