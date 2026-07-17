from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Mapping
from .market_data_reconciliation_policy import MarketDataReconciliationPolicy
from .market_data_reconciliation_profile import (
    MarketDataReconciliationProfile, MarketDataReconciliationSummary,
    MarketDataSnapshot, ReconciliationCheckProfile,
)

def _value(obj: Any, name: str, default: Any = None) -> Any:
    return obj.get(name, default) if isinstance(obj, Mapping) else getattr(obj, name, default)

def _parse(value: str | datetime) -> datetime:
    result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)

def to_snapshot(obj: Any, source: str) -> MarketDataSnapshot | None:
    if obj is None:
        return None
    if isinstance(obj, MarketDataSnapshot):
        return obj
    timestamp = _value(obj, "timestamp", _value(obj, "exchange_timestamp", _value(obj, "date", None)))
    price = _value(obj, "price", _value(obj, "close", _value(obj, "midpoint", None)))
    if timestamp is None or price is None:
        return None
    return MarketDataSnapshot(
        symbol=str(_value(obj, "symbol", "")).strip().upper(),
        timestamp=_parse(timestamp).isoformat(),
        price=float(price),
        volume=float(_value(obj, "volume", _value(obj, "size", 0.0)) or 0.0),
        source=source,
        asset_class=str(_value(obj, "asset_class", "EQUITY")).upper(),
        metadata=dict(_value(obj, "metadata", {}) or {}),
    )

class MarketDataReconciliationEngine:
    def __init__(self, policy: MarketDataReconciliationPolicy | None = None) -> None:
        self.policy = policy or MarketDataReconciliationPolicy()
        self.policy.validate()

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95: return "A", "LOW"
        if score >= 85: return "B", "MODERATE"
        if score >= 70: return "C", "SEVERE"
        return "F", "CRITICAL"

    def evaluate(self, live: Any, historical: Any) -> MarketDataReconciliationProfile:
        l, h = to_snapshot(live, "live"), to_snapshot(historical, "historical")
        checks: list[ReconciliationCheckProfile] = []
        warnings: list[str] = []
        def add(name: str, passed: bool, message: str, required: bool = True, metadata=None) -> None:
            checks.append(ReconciliationCheckProfile(name, bool(passed), required, 100.0 if passed else 0.0, "LOW" if passed else "CRITICAL", message, metadata or {}))
        add("live_snapshot", l is not None or not self.policy.require_live_value, "Live snapshot is available.")
        add("historical_snapshot", h is not None or not self.policy.require_historical_value, "Historical snapshot is available.")
        if l is None or h is None:
            failed = [x for x in checks if x.required and not x.passed]
            score = sum(x.score for x in checks) / len(checks)
            grade, severity = self._grade(score)
            return MarketDataReconciliationProfile(False, False, l.symbol if l else h.symbol if h else "", score, grade, severity, "REJECT", None, None, None, None, None, tuple(checks), rejection_reasons=tuple(x.name.upper() for x in failed), live_snapshot=l, historical_snapshot=h)
        add("symbol_match", l.symbol == h.symbol or not self.policy.reject_symbol_mismatch, "Symbols match.")
        pdiff = l.price - h.price
        ppct = abs(pdiff) / abs(h.price) if h.price else 0.0
        add("price_difference", ppct <= self.policy.maximum_price_difference_pct, "Prices are within tolerance.", metadata={"difference_pct": ppct})
        if ppct <= self.policy.maximum_price_difference_pct and ppct > self.policy.warning_price_difference_pct:
            warnings.append("PRICE_DIFFERENCE_WARNING")
        vdiff = l.volume - h.volume
        vpct = abs(vdiff) / abs(h.volume) if h.volume else 0.0
        add("volume_difference", vpct <= self.policy.maximum_volume_difference_pct, "Volumes are within tolerance.", metadata={"difference_pct": vpct})
        if vpct <= self.policy.maximum_volume_difference_pct and vpct > self.policy.warning_volume_difference_pct:
            warnings.append("VOLUME_DIFFERENCE_WARNING")
        tdiff = abs((_parse(l.timestamp) - _parse(h.timestamp)).total_seconds())
        add("timestamp_difference", tdiff <= self.policy.maximum_timestamp_difference_seconds or not self.policy.reject_timestamp_mismatch, "Timestamps are within tolerance.", metadata={"difference_seconds": tdiff})
        required = [x for x in checks if x.required]
        failed = [x for x in required if not x.passed]
        score = sum(x.score for x in required) / len(required)
        allowed = not failed and score >= self.policy.minimum_reconciliation_score
        if not self.policy.fail_closed:
            allowed = score >= self.policy.minimum_reconciliation_score
        grade, severity = self._grade(score)
        return MarketDataReconciliationProfile(True, allowed, l.symbol, round(score, 2), grade, severity, "ACCEPT" if allowed else "REJECT", pdiff, ppct, vdiff, vpct, tdiff, tuple(checks), tuple(warnings), tuple(x.name.upper() for x in failed), l, h)

    def evaluate_many(self, pairs) -> MarketDataReconciliationSummary:
        profiles = tuple(self.evaluate(a, b) for a, b in pairs)
        total = len(profiles)
        matched = sum(p.allowed for p in profiles)
        rejected = total - matched
        score = sum(p.score for p in profiles) / total if total else 0.0
        grade, severity = self._grade(score)
        return MarketDataReconciliationSummary(
            valid=total > 0, allowed=total > 0 and rejected == 0,
            total_count=total, matched_count=matched,
            warning_count=sum(bool(p.warnings) for p in profiles),
            rejected_count=rejected, score=round(score, 2), grade=grade,
            severity=severity, recommendation="ACCEPT" if total > 0 and rejected == 0 else "REVIEW",
            profiles=profiles,
            warnings=tuple(f"{p.symbol}:{w}" for p in profiles for w in p.warnings),
            rejection_reasons=tuple(f"{p.symbol}:{r}" for p in profiles for r in p.rejection_reasons),
        )
