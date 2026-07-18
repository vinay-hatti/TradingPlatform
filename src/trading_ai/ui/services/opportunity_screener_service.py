from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters
from trading_ai.ui.models.opportunity import (
    OpportunityFilterOptions,
    OpportunityRecord,
    OpportunityScreenerResponse,
)


def value(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            candidate = obj.get(name)
            if candidate not in (None, ""):
                return candidate
    return default


def number(raw: Any, default: float | None = None) -> float | None:
    try:
        if raw in (None, ""):
            return default
        text = str(raw).replace("$", "").replace(",", "").replace("%", "").strip()
        return float(text)
    except (TypeError, ValueError):
        return default


def integer(raw: Any, default: int | None = None) -> int | None:
    result = number(raw, None)
    return int(result) if result is not None else default


def probability(raw: Any) -> float | None:
    result = number(raw, None)
    if result is None:
        return None
    if result > 1:
        result /= 100.0
    return max(0.0, min(1.0, result))


def direction(raw: Any) -> str:
    text = str(raw or "").upper()
    if "CALL" in text or text in {"BUY", "LONG", "BULLISH"}:
        return "CALL"
    if "PUT" in text or text in {"SELL", "SHORT", "BEARISH"}:
        return "PUT"
    return "WATCH"


def build_contract(row: dict[str, Any]) -> str | None:
    explicit = value(
        row,
        "contract",
        "contract_ticker",
        "option_symbol",
        "selected_contract",
        default=None,
    )
    if explicit:
        return str(explicit)

    strike = value(row, "strike", "selected_strike", default=None)
    expiry = value(row, "expiry", "expiration", "selected_expiry", default=None)
    option_type = value(row, "option_type", default=None)
    parts = [str(item) for item in (strike, option_type, expiry) if item not in (None, "")]
    return " ".join(parts) if parts else None


class OpportunityScreenerService:
    SORT_FIELDS = {
        "rank",
        "symbol",
        "score",
        "probability_of_profit",
        "expected_value",
        "liquidity_score",
        "spread_pct",
        "volume",
        "open_interest",
        "expiry",
    }

    def __init__(
        self,
        adapters: RepositoryArtifactAdapters | None = None,
        stale_after_seconds: int = 3600,
    ) -> None:
        self.adapters = adapters or RepositoryArtifactAdapters()
        self.stale_after_seconds = stale_after_seconds

    def _source(self):
        optimized = self.adapters.optimized_portfolio()
        if optimized.available and optimized.data:
            return optimized
        return self.adapters.scanner()

    def _normalize(self) -> tuple[list[OpportunityRecord], Any]:
        source = self._source()
        records: list[OpportunityRecord] = []

        for row in source.data or []:
            symbol = str(value(row, "symbol", "ticker", default="")).upper()
            if not symbol:
                continue

            score = number(
                value(
                    row,
                    "rank_score",
                    "ai_score",
                    "adjusted_score",
                    "option_score",
                    "score",
                    default=0,
                ),
                0.0,
            ) or 0.0
            if score <= 1:
                score *= 100.0

            raw_notes = value(
                row,
                "notes",
                "portfolio_notes",
                "rejection_reasons",
                "warnings",
                default="",
            )
            notes = [
                item.strip()
                for item in str(raw_notes).replace("|", ";").split(";")
                if item.strip()
            ]

            status = str(value(row, "status", default="ACCEPTED")).upper()
            strategy = str(
                value(
                    row,
                    "strategy",
                    "selected_strategy",
                    "recommended_strategy",
                    default="Directional",
                )
            )

            record = OpportunityRecord(
                rank=1,
                symbol=symbol,
                direction=direction(
                    value(
                        row,
                        "signal",
                        "direction",
                        "recommendation",
                        "option_type",
                        default="WATCH",
                    )
                ),
                strategy=strategy,
                score=max(0.0, min(100.0, score)),
                probability_of_profit=probability(
                    value(
                        row,
                        "probability_of_profit",
                        "win_probability",
                        "calibrated_probability",
                        "pop",
                        default=None,
                    )
                ),
                expected_value=number(
                    value(
                        row,
                        "expected_value",
                        "expected_return",
                        "expected_edge",
                        default=None,
                    ),
                    None,
                ),
                regime=str(
                    value(
                        row,
                        "regime",
                        "market_regime",
                        "current_regime",
                        default="Unknown",
                    )
                ),
                status=status,
                contract=build_contract(row),
                expiry=(
                    str(value(row, "expiry", "expiration", "selected_expiry"))
                    if value(row, "expiry", "expiration", "selected_expiry") is not None
                    else None
                ),
                strike=number(
                    value(row, "strike", "selected_strike", default=None),
                    None,
                ),
                option_type=(
                    str(value(row, "option_type"))
                    if value(row, "option_type") is not None
                    else None
                ),
                bid=number(value(row, "bid", default=None), None),
                ask=number(value(row, "ask", default=None), None),
                spread_pct=number(
                    value(
                        row,
                        "spread_pct",
                        "bid_ask_spread_pct",
                        "selected_spread_pct",
                        default=None,
                    ),
                    None,
                ),
                volume=integer(
                    value(row, "volume", "option_volume", default=None),
                    None,
                ),
                open_interest=integer(
                    value(
                        row,
                        "open_interest",
                        "option_open_interest",
                        default=None,
                    ),
                    None,
                ),
                implied_volatility=number(
                    value(
                        row,
                        "implied_volatility",
                        "iv",
                        default=None,
                    ),
                    None,
                ),
                delta=number(value(row, "delta", default=None), None),
                gamma=number(value(row, "gamma", default=None), None),
                theta=number(value(row, "theta", default=None), None),
                vega=number(value(row, "vega", default=None), None),
                liquidity_score=number(
                    value(
                        row,
                        "liquidity_score",
                        "execution_liquidity_score",
                        default=None,
                    ),
                    None,
                ),
                confidence_grade=(
                    str(
                        value(
                            row,
                            "confidence_grade",
                            "recommendation_grade",
                            default="",
                        )
                    )
                    or None
                ),
                source=source.source,
                as_of=source.as_of,
                notes=notes,
            )
            records.append(record)

        records.sort(
            key=lambda item: (
                item.score,
                item.probability_of_profit or 0.0,
                item.liquidity_score or 0.0,
            ),
            reverse=True,
        )
        for index, record in enumerate(records, start=1):
            record.rank = index

        return records, source

    @staticmethod
    def _filter_options(records: list[OpportunityRecord]) -> OpportunityFilterOptions:
        return OpportunityFilterOptions(
            symbols=sorted({item.symbol for item in records}),
            directions=sorted({item.direction for item in records}),
            regimes=sorted({item.regime for item in records}),
            strategies=sorted({item.strategy for item in records}),
            sources=sorted({item.source for item in records}),
        )

    def query(
        self,
        *,
        search: str | None = None,
        symbol: str | None = None,
        direction_filter: str | None = None,
        regime: str | None = None,
        strategy: str | None = None,
        status: str | None = None,
        min_score: float | None = None,
        min_pop: float | None = None,
        max_spread_pct: float | None = None,
        min_volume: int | None = None,
        min_open_interest: int | None = None,
        sort_by: str = "score",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 25,
    ) -> OpportunityScreenerResponse:
        records, source = self._normalize()
        all_records = list(records)

        if search:
            needle = search.lower().strip()
            records = [
                item for item in records
                if needle in item.symbol.lower()
                or needle in item.strategy.lower()
                or needle in item.regime.lower()
                or needle in (item.contract or "").lower()
                or any(needle in note.lower() for note in item.notes)
            ]
        if symbol:
            symbols = {item.strip().upper() for item in symbol.split(",") if item.strip()}
            records = [item for item in records if item.symbol in symbols]
        if direction_filter:
            directions = {
                item.strip().upper()
                for item in direction_filter.split(",")
                if item.strip()
            }
            records = [item for item in records if item.direction in directions]
        if regime:
            regimes = {item.strip().lower() for item in regime.split(",") if item.strip()}
            records = [item for item in records if item.regime.lower() in regimes]
        if strategy:
            strategies = {
                item.strip().lower()
                for item in strategy.split(",")
                if item.strip()
            }
            records = [item for item in records if item.strategy.lower() in strategies]
        if status:
            statuses = {item.strip().upper() for item in status.split(",") if item.strip()}
            records = [item for item in records if item.status in statuses]
        if min_score is not None:
            records = [item for item in records if item.score >= min_score]
        if min_pop is not None:
            normalized = min_pop / 100.0 if min_pop > 1 else min_pop
            records = [
                item for item in records
                if item.probability_of_profit is not None
                and item.probability_of_profit >= normalized
            ]
        if max_spread_pct is not None:
            records = [
                item for item in records
                if item.spread_pct is not None
                and item.spread_pct <= max_spread_pct
            ]
        if min_volume is not None:
            records = [
                item for item in records
                if item.volume is not None and item.volume >= min_volume
            ]
        if min_open_interest is not None:
            records = [
                item for item in records
                if item.open_interest is not None
                and item.open_interest >= min_open_interest
            ]

        sort_by = sort_by if sort_by in self.SORT_FIELDS else "score"
        descending = sort_order.lower() != "asc"

        def sort_value(item: OpportunityRecord):
            raw = getattr(item, sort_by, None)
            if raw is None:
                return float("-inf") if descending else float("inf")
            return raw

        records.sort(key=sort_value, reverse=descending)
        for index, record in enumerate(records, start=1):
            record.rank = index

        page = max(1, page)
        page_size = max(1, min(200, page_size))
        total_pages = max(1, math.ceil(len(records) / page_size))
        page = min(page, total_pages)
        start = (page - 1) * page_size
        page_records = records[start:start + page_size]

        now = datetime.now(timezone.utc)
        age_seconds = max(0.0, (now - source.as_of).total_seconds())

        return OpportunityScreenerResponse(
            generated_at=now,
            total_records=len(all_records),
            filtered_records=len(records),
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            sort_by=sort_by,
            sort_order="desc" if descending else "asc",
            records=page_records,
            filters=self._filter_options(all_records),
            source_detail=source.detail,
            stale=age_seconds > self.stale_after_seconds,
            age_seconds=round(age_seconds, 2),
        )
