from __future__ import annotations
import csv, math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any
from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters
from trading_ai.ui.models.symbol_intelligence import (
    PricePoint, SymbolIntelligenceResponse, SymbolOpportunity, TechnicalSnapshot,
)

def val(row: Any, *names: str, default=None):
    for name in names:
        candidate = row.get(name) if isinstance(row, dict) else getattr(row, name, None)
        if candidate not in (None, ""):
            return candidate
    return default

def num(raw, default=None):
    try:
        if raw in (None, ""):
            return default
        return float(str(raw).replace("$","").replace(",","").replace("%","").strip())
    except (TypeError, ValueError):
        return default

def integer(raw, default=None):
    value = num(raw)
    return int(value) if value is not None else default

def probability(raw):
    value = num(raw)
    if value is None:
        return None
    return max(0.0, min(1.0, value / 100.0 if value > 1 else value))

def sma(values, period):
    return mean(values[-period:]) if len(values) >= period else None

def rsi(values, period=14):
    if len(values) <= period:
        return None
    changes = [values[i] - values[i-1] for i in range(1, len(values))]
    window = changes[-period:]
    gain = mean([max(x, 0.0) for x in window])
    loss = mean([max(-x, 0.0) for x in window])
    if loss == 0:
        return 100.0
    rs = gain / loss
    return 100.0 - 100.0 / (1.0 + rs)

def atr(rows, period=14):
    if len(rows) <= period:
        return None
    values = []
    for i in range(1, len(rows)):
        current, previous = rows[i], rows[i-1]
        values.append(max(
            current.high-current.low,
            abs(current.high-previous.close),
            abs(current.low-previous.close),
        ))
    return mean(values[-period:])

class RepositoryPriceHistorySource:
    def get_range(self, symbol: str, start: date, end: date):
        from trading_ai.database import create_session
        from trading_ai.database.repositories import PriceHistoryRepository
        session = create_session()
        try:
            return PriceHistoryRepository(session).get_range(symbol.upper(), start, end)
        finally:
            session.close()

class SymbolIntelligenceService:
    PATTERNS = (
        "optimized_portfolio_*.csv",
        "scanner_results_*.csv",
        "daily/**/*.csv",
        "daily_recommendations/**/*.csv",
        "recommendations/**/*.csv",
        "**/live_trade_candidates.csv",
    )

    def __init__(self, prices=None, artifacts=None, stale_after_seconds=86400):
        self.prices = prices or RepositoryPriceHistorySource()
        self.artifacts = artifacts or RepositoryArtifactAdapters()
        self.stale_after_seconds = stale_after_seconds

    def _prices(self, symbol, days):
        end = date.today()
        start = end - timedelta(days=max(days * 2, 400))
        rows = self.prices.get_range(symbol, start, end)
        points = [PricePoint(
            date=val(row, "date"),
            open=float(val(row, "open", default=0)),
            high=float(val(row, "high", default=0)),
            low=float(val(row, "low", default=0)),
            close=float(val(row, "close", default=0)),
            volume=int(val(row, "volume", default=0)),
        ) for row in rows]
        return points[-days:]

    def _technicals(self, rows):
        if not rows:
            return TechnicalSnapshot()
        closes = [x.close for x in rows]
        returns = [math.log(closes[i]/closes[i-1]) for i in range(1, len(closes))
                   if closes[i] > 0 and closes[i-1] > 0]
        current = closes[-1]
        s20, s50, s200 = sma(closes,20), sma(closes,50), sma(closes,200)
        trend = "BULLISH" if s20 and s50 and current > s20 > s50 else (
            "BEARISH" if s20 and s50 and current < s20 < s50 else "MIXED"
        )
        regime = "TREND_UP" if trend == "BULLISH" else (
            "TREND_DOWN" if trend == "BEARISH" else "CHOP"
        )
        def change(period):
            return None if len(closes) <= period or closes[-period-1] == 0 else (
                current / closes[-period-1] - 1.0
            ) * 100.0
        high, low = max(x.high for x in rows), min(x.low for x in rows)
        return TechnicalSnapshot(
            close=current,
            change_1d_pct=change(1),
            change_5d_pct=change(5),
            change_20d_pct=change(20),
            high_52w=high,
            low_52w=low,
            distance_from_high_pct=(current/high-1.0)*100.0 if high else None,
            average_volume_20d=mean([x.volume for x in rows[-20:]]),
            realized_volatility_20d=pstdev(returns[-20:])*math.sqrt(252)*100.0 if len(returns) >= 2 else None,
            sma20=s20, sma50=s50, sma200=s200,
            rsi14=rsi(closes), atr14=atr(rows),
            trend=trend, regime=regime,
        )

    def _candidate_files(self):
        reports = self.artifacts.root / "reports"
        found = {}
        for pattern in self.PATTERNS:
            for path in reports.glob(pattern):
                if path.is_file():
                    found[str(path.resolve())] = path
        return sorted(found.values(), key=lambda p: p.stat().st_mtime, reverse=True)[:100]

    def _opportunity_from_row(self, row, path):
        raw_signal = str(val(row, "signal", "direction", "recommendation", "option_type", default="WATCH")).upper()
        source = "optimized_portfolio_artifact" if "optimized_portfolio" in path.name else (
            "scanner_artifact" if "scanner_results" in path.name else "daily_trade_candidate_artifact"
        )
        return SymbolOpportunity(
            signal="CALL" if "CALL" in raw_signal else "PUT" if "PUT" in raw_signal else "WATCH",
            strategy=str(val(row, "strategy", "selected_strategy", "recommended_strategy", default="Unknown")),
            score=num(val(row, "rank_score", "adjusted_score", "option_score", "score")),
            ai_score=num(val(row, "ai_score")),
            probability_of_profit=probability(val(row, "probability_of_profit", "win_probability", "calibrated_probability", "pop")),
            contract=str(val(row, "contract", "contract_ticker", "option_symbol", default="")) or None,
            strike=num(val(row, "strike", "selected_strike")),
            expiry=str(val(row, "expiry", "expiration", "selected_expiry", default="")) or None,
            bid=num(val(row, "bid")),
            ask=num(val(row, "ask")),
            spread_pct=num(val(row, "spread_pct", "bid_ask_spread_pct", "selected_spread_pct")),
            open_interest=integer(val(row, "open_interest", "option_open_interest")),
            option_volume=integer(val(row, "option_volume", "volume")),
            implied_volatility=num(val(row, "implied_volatility", "iv", "volatility")),
            delta=num(val(row, "delta")), gamma=num(val(row, "gamma")),
            theta=num(val(row, "theta")), vega=num(val(row, "vega")),
            liquidity_score=num(val(row, "liquidity_score")),
            ranking_reason=str(val(row, "ranking_reason", "notes", "trade_notes", default="")) or None,
            source=source,
            as_of=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
        )

    def _opportunities(self, symbol):
        matches = []
        files = self._candidate_files()
        for path in files:
            try:
                with path.open("r", encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
            except Exception:
                continue
            for row in rows:
                row_symbol = str(val(
                    row, "symbol", "ticker", "underlying_symbol", "underlying", default=""
                )).strip().upper()
                if row_symbol == symbol:
                    matches.append((path, row))
        matches.sort(key=lambda item: item[0].stat().st_mtime, reverse=True)
        return (
            [self._opportunity_from_row(row, path) for path, row in matches[:20]],
            f"Searched {len(files)} recent report CSV files; found {len(matches)} rows for {symbol}.",
        )

    def get(self, symbol, days=252):
        symbol = symbol.strip().upper()
        notices = []
        try:
            prices = self._prices(symbol, days)
        except Exception as exc:
            prices = []
            notices.append(f"Price history unavailable: {type(exc).__name__}: {exc}")
        opportunities, detail = self._opportunities(symbol)
        notices.append(detail)
        price_as_of = datetime.combine(
            prices[-1].date, datetime.min.time(), tzinfo=timezone.utc
        ) if prices else None
        age = max(0.0, (datetime.now(timezone.utc)-price_as_of).total_seconds()) if price_as_of else None
        if not prices:
            notices.append(f"No database price history found for {symbol}.")
        if not opportunities:
            notices.append(f"No scanner, optimized-portfolio, or daily-candidate opportunity found for {symbol}.")
        return SymbolIntelligenceResponse(
            generated_at=datetime.now(timezone.utc),
            symbol=symbol,
            price_source="PriceHistoryRepository" if prices else "Unavailable",
            price_as_of=price_as_of,
            stale=age is None or age > self.stale_after_seconds,
            age_seconds=round(age,2) if age is not None else None,
            technicals=self._technicals(prices),
            latest_opportunity=opportunities[0] if opportunities else None,
            opportunity_history=opportunities,
            price_history=prices,
            notices=notices,
        )
