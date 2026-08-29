from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

from .contracts import BarrierOutcomeLabel
from .policy import OutcomeProbabilityPolicy


def _number(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def _bar(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    return {
        "date": getattr(row, "date"),
        "open": getattr(row, "open", None),
        "high": getattr(row, "high", None),
        "low": getattr(row, "low", None),
        "close": getattr(row, "close", None),
    }


class BarrierOutcomeLabeler:
    """Realizes daily-bar labels without assuming intraday order.

    The governed entry is the first overlap with the published entry zone during
    the entry window. Barrier evaluation begins on the following session. If a
    target and stop are both crossed by the same daily bar, that target is marked
    ambiguous and excluded from binary model training.
    """

    version = "M77.0-DAILY-BARRIER-LABELS-1.0"

    def __init__(self, policy: OutcomeProbabilityPolicy | None = None):
        self.policy = policy or OutcomeProbabilityPolicy()
        self.policy.validate()

    def label(
        self,
        *,
        candidate_id: str,
        scanner_run_id: str,
        candidate_payload: dict[str, Any],
        future_bars: Iterable[Any],
    ) -> BarrierOutcomeLabel:
        symbol = str(candidate_payload.get("symbol") or "").upper()
        as_of = str(candidate_payload.get("snapshot_timestamp") or "")
        if not as_of:
            return self._empty("INVALID_SNAPSHOT_TIMESTAMP", candidate_id, scanner_run_id, symbol, as_of)
        try:
            as_of_date = _date(as_of)
        except (TypeError, ValueError):
            return self._empty("INVALID_SNAPSHOT_TIMESTAMP", candidate_id, scanner_run_id, symbol, as_of)
        bars = sorted(
            (_bar(row) for row in future_bars if _date(_bar(row)["date"]) > as_of_date),
            key=lambda row: _date(row["date"]),
        )[: self.policy.horizon_sessions + self.policy.entry_window_sessions]
        if len(bars) < self.policy.horizon_sessions:
            return self._empty(
                "PENDING_HORIZON",
                candidate_id,
                scanner_run_id,
                symbol,
                as_of,
                horizon_end=str(bars[-1]["date"]) if bars else None,
                evidence={"available_sessions": len(bars), "required_sessions": self.policy.horizon_sessions},
            )

        geometry = self._geometry(candidate_payload)
        if geometry is None:
            return self._empty("INVALID_GEOMETRY", candidate_id, scanner_run_id, symbol, as_of)
        bullish, preferred, zone_low, zone_high, stop, targets = geometry

        entry_index = None
        entry_price = None
        for index, row in enumerate(bars[: self.policy.entry_window_sessions]):
            high = _number(row.get("high"))
            low = _number(row.get("low"))
            if high is None or low is None:
                continue
            if low <= zone_high and high >= zone_low:
                entry_index = index
                entry_price = min(high, max(low, preferred))
                break
        if entry_index is None or entry_price is None:
            return self._empty(
                "NO_ENTRY",
                candidate_id,
                scanner_run_id,
                symbol,
                as_of,
                horizon_end=str(bars[self.policy.horizon_sessions - 1]["date"]),
                entry_triggered=0,
                evidence={"entry_zone": [zone_low, zone_high], "entry_window_sessions": self.policy.entry_window_sessions},
            )

        # Entry-day OHLC ordering is unknowable. Start path evaluation next day.
        path = bars[entry_index + 1 : entry_index + 1 + self.policy.horizon_sessions]
        if len(path) < self.policy.horizon_sessions:
            return self._empty(
                "PENDING_HORIZON",
                candidate_id,
                scanner_run_id,
                symbol,
                as_of,
                horizon_end=str(path[-1]["date"]) if path else None,
                entry_triggered=1,
                evidence={
                    "available_post_entry_sessions": len(path),
                    "required_post_entry_sessions": self.policy.horizon_sessions,
                    "entry_date": str(bars[entry_index]["date"]),
                },
            )

        stop_day = self._first_cross(path, stop, bullish=bullish, target=False)
        target_days = [self._first_cross(path, target, bullish=bullish, target=True) for target in targets]
        labels: list[int | None] = []
        ambiguous: list[str] = []
        for index, target_day in enumerate(target_days, start=1):
            if target_day is not None and stop_day is not None and target_day == stop_day:
                labels.append(None)
                ambiguous.append(f"TARGET_{index}_AND_STOP_SAME_DAILY_BAR")
            elif target_day is not None and (stop_day is None or target_day < stop_day):
                labels.append(1)
            elif stop_day is not None and (target_day is None or stop_day < target_day):
                labels.append(0)
            else:
                labels.append(None)
        while len(labels) < 3:
            labels.append(None)
            target_days.append(None)

        highs = [_number(row.get("high")) for row in path]
        lows = [_number(row.get("low")) for row in path]
        highs = [value for value in highs if value is not None]
        lows = [value for value in lows if value is not None]
        last_close = _number(path[-1].get("close"), entry_price) or entry_price
        if bullish:
            mfe = (max(highs, default=entry_price) - entry_price) / entry_price * 100.0
            mae = (entry_price - min(lows, default=entry_price)) / entry_price * 100.0
            realized = (last_close - entry_price) / entry_price * 100.0
        else:
            mfe = (entry_price - min(lows, default=entry_price)) / entry_price * 100.0
            mae = (max(highs, default=entry_price) - entry_price) / entry_price * 100.0
            realized = (entry_price - last_close) / entry_price * 100.0

        status = "REALIZED"
        if ambiguous:
            status = "PARTIALLY_AMBIGUOUS"
        elif labels[0] is None:
            status = "CENSORED"
        if stop_day is None:
            thesis_invalidation = 0
        elif target_days[0] is None or stop_day < target_days[0]:
            thesis_invalidation = 1
        elif stop_day == target_days[0]:
            thesis_invalidation = None
        else:
            thesis_invalidation = 0
        return BarrierOutcomeLabel(
            status=status,
            candidate_id=candidate_id,
            scanner_run_id=scanner_run_id,
            symbol=symbol,
            as_of=as_of,
            horizon_end=str(path[-1]["date"]),
            entry_triggered=1,
            target_1_before_stop=labels[0],
            target_2_before_stop=labels[1],
            target_3_before_stop=labels[2],
            profitable_at_horizon=1 if realized > 0 else 0,
            thesis_invalidation=thesis_invalidation,
            maximum_favorable_excursion_pct=round(max(0.0, mfe), 6),
            maximum_adverse_excursion_pct=round(max(0.0, mae), 6),
            realized_return_pct=round(realized, 6),
            days_to_target_1=None if target_days[0] is None else target_days[0] + 1,
            days_to_target_2=None if target_days[1] is None else target_days[1] + 1,
            days_to_stop=None if stop_day is None else stop_day + 1,
            entry_date=str(bars[entry_index]["date"]),
            entry_price=round(entry_price, 6),
            ambiguous_targets=tuple(ambiguous),
            evidence={
                "version": self.version,
                "direction": "BULLISH" if bullish else "BEARISH",
                "entry_zone": [zone_low, zone_high],
                "preferred_entry": preferred,
                "stop": stop,
                "targets": targets,
                "barrier_evaluation_begins_after_entry_session": True,
                "same_bar_order_assumed": False,
                "horizon_sessions": self.policy.horizon_sessions,
            },
        )

    @staticmethod
    def _first_cross(path: list[dict[str, Any]], level: float, *, bullish: bool, target: bool) -> int | None:
        for index, row in enumerate(path):
            high = _number(row.get("high"))
            low = _number(row.get("low"))
            if high is None or low is None:
                continue
            crossed = (
                high >= level if bullish and target
                else low <= level if bullish
                else low <= level if target
                else high >= level
            )
            if crossed:
                return index
        return None

    @staticmethod
    def _geometry(payload: dict[str, Any]) -> tuple[bool, float, float, float, float, list[float]] | None:
        plan = payload.get("trade_plan") or {}
        entry = plan.get("entry") or {}
        stop_payload = plan.get("stop") or {}
        target_payload = plan.get("targets") or {}
        preferred = _number(entry.get("preferred_entry"))
        zone_low = _number(entry.get("zone_low"), preferred)
        zone_high = _number(entry.get("zone_high"), preferred)
        stop = _number(stop_payload.get("recommended_stop"))
        targets = [
            _number(item.get("price") if isinstance(item, dict) else item)
            for item in (target_payload.get("targets") or [])[:3]
        ]
        targets = [value for value in targets if value is not None and value > 0]
        if preferred is None or zone_low is None or zone_high is None or stop is None or not targets:
            return None
        bullish = "BULL" in str(payload.get("direction") or "").upper()
        bearish = "BEAR" in str(payload.get("direction") or "").upper()
        if not bullish and not bearish:
            return None
        valid = stop < preferred and all(target > preferred for target in targets) if bullish else stop > preferred and all(target < preferred for target in targets)
        if not valid:
            return None
        return bullish, preferred, min(zone_low, zone_high), max(zone_low, zone_high), stop, targets

    @staticmethod
    def _empty(
        status: str,
        candidate_id: str,
        scanner_run_id: str,
        symbol: str,
        as_of: str,
        *,
        horizon_end: str | None = None,
        entry_triggered: int | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> BarrierOutcomeLabel:
        return BarrierOutcomeLabel(
            status=status,
            candidate_id=candidate_id,
            scanner_run_id=scanner_run_id,
            symbol=symbol,
            as_of=as_of,
            horizon_end=horizon_end,
            entry_triggered=entry_triggered,
            target_1_before_stop=None,
            target_2_before_stop=None,
            target_3_before_stop=None,
            profitable_at_horizon=None,
            thesis_invalidation=None,
            maximum_favorable_excursion_pct=None,
            maximum_adverse_excursion_pct=None,
            realized_return_pct=None,
            days_to_target_1=None,
            days_to_target_2=None,
            days_to_stop=None,
            entry_date=None,
            entry_price=None,
            evidence=dict(evidence or {}),
        )
