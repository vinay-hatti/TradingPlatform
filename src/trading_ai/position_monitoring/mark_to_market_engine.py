from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import uuid

from .position_monitoring_policy import PositionMonitoringPolicy
from .position_monitoring_profile import (
    IntradayRiskState,
    MarkedPositionSnapshot,
    RealTimePositionSnapshot,
    RealTimeQuoteSnapshot,
)


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class MarkToMarketEngine:
    def __init__(
        self,
        policy: PositionMonitoringPolicy | None = None,
    ) -> None:
        self.policy = policy or PositionMonitoringPolicy()
        self.policy.validate()

    @staticmethod
    def _direction(position: RealTimePositionSnapshot) -> float:
        if position.quantity < 0 or position.side.upper() == "SHORT":
            return -1.0
        return 1.0

    def quote_is_stale(
        self,
        quote: RealTimeQuoteSnapshot,
        *,
        as_of: datetime,
    ) -> bool:
        age = (as_of - _parse_timestamp(quote.timestamp)).total_seconds()
        return age > self.policy.maximum_quote_age_seconds

    def mark_position(
        self,
        position: RealTimePositionSnapshot,
        quote: RealTimeQuoteSnapshot,
        *,
        as_of: datetime,
    ) -> MarkedPositionSnapshot:
        mark_price = quote.midpoint
        if self.policy.require_positive_mark_price and mark_price <= 0:
            raise ValueError(
                f"Non-positive mark price for position {position.position_id}"
            )

        direction = self._direction(position)
        absolute_quantity = abs(float(position.quantity))
        multiplier = max(int(position.multiplier or 1), 1)
        cost_basis = absolute_quantity * position.average_cost * multiplier
        signed_quantity = absolute_quantity * direction
        market_value = signed_quantity * mark_price * multiplier
        signed_exposure = market_value
        unrealized = (
            (mark_price - position.average_cost)
            * absolute_quantity
            * multiplier
            * direction
        )
        realized = float(position.realized_pnl)
        return MarkedPositionSnapshot(
            position_id=position.position_id,
            account_id=position.account_id,
            symbol=position.symbol,
            underlying_symbol=position.underlying_symbol,
            asset_class=position.asset_class,
            side="LONG" if direction > 0 else "SHORT",
            quantity=position.quantity,
            average_cost=round(position.average_cost, 6),
            mark_price=round(mark_price, 6),
            multiplier=multiplier,
            cost_basis=round(cost_basis, 6),
            market_value=round(market_value, 6),
            signed_exposure=round(signed_exposure, 6),
            realized_pnl=round(realized, 6),
            unrealized_pnl=round(unrealized, 6),
            total_pnl=round(realized + unrealized, 6),
            total_commissions=round(position.total_commissions, 6),
            quote_timestamp=quote.timestamp,
            quote_source=quote.source,
            stale_quote=self.quote_is_stale(quote, as_of=as_of),
            sector=position.sector,
            strategy_name=position.strategy_name,
            metadata=dict(position.metadata),
        )

    def aggregate(
        self,
        *,
        account_id: str,
        starting_equity: float,
        peak_equity: float,
        cash_balance: float,
        positions: tuple[RealTimePositionSnapshot, ...],
        quotes: dict[str, RealTimeQuoteSnapshot],
        as_of: datetime | None = None,
        snapshot_id: str | None = None,
    ) -> IntradayRiskState:
        now = as_of or datetime.now(timezone.utc)
        marked = []
        missing_quote_count = 0

        for position in positions:
            quote = quotes.get(position.symbol)
            if quote is None:
                missing_quote_count += 1
                continue
            marked.append(
                self.mark_position(position, quote, as_of=now)
            )

        realized = sum(item.realized_pnl for item in marked)
        unrealized = sum(item.unrealized_pnl for item in marked)
        long_exposure = sum(
            item.signed_exposure
            for item in marked
            if item.signed_exposure > 0
        )
        short_exposure = sum(
            abs(item.signed_exposure)
            for item in marked
            if item.signed_exposure < 0
        )
        gross_exposure = long_exposure + short_exposure
        net_exposure = long_exposure - short_exposure
        current_equity = starting_equity + realized + unrealized
        peak = max(peak_equity, current_equity)
        drawdown = max(0.0, peak - current_equity)
        drawdown_pct = (
            drawdown / starting_equity
            if starting_equity > 0
            else None
        )

        by_symbol = defaultdict(float)
        by_underlying = defaultdict(float)
        by_sector = defaultdict(float)
        by_strategy = defaultdict(float)

        for item in marked:
            by_symbol[item.symbol] += item.signed_exposure
            by_underlying[item.underlying_symbol] += item.signed_exposure
            by_sector[item.sector or "UNCLASSIFIED"] += item.signed_exposure
            by_strategy[item.strategy_name or "UNCLASSIFIED"] += (
                item.signed_exposure
            )

        return IntradayRiskState(
            account_id=account_id,
            snapshot_id=snapshot_id or f"snapshot-{uuid.uuid4().hex}",
            starting_equity=round(starting_equity, 6),
            peak_equity=round(peak, 6),
            current_equity=round(current_equity, 6),
            cash_balance=round(cash_balance, 6),
            realized_pnl=round(realized, 6),
            unrealized_pnl=round(unrealized, 6),
            total_pnl=round(realized + unrealized, 6),
            gross_exposure=round(gross_exposure, 6),
            net_exposure=round(net_exposure, 6),
            long_exposure=round(long_exposure, 6),
            short_exposure=round(short_exposure, 6),
            intraday_drawdown=round(drawdown, 6),
            drawdown_pct=drawdown_pct,
            open_position_count=len(marked),
            stale_position_count=sum(item.stale_quote for item in marked),
            missing_quote_count=missing_quote_count,
            marked_positions=tuple(marked),
            by_symbol={
                key: round(value, 6) for key, value in by_symbol.items()
            },
            by_underlying={
                key: round(value, 6)
                for key, value in by_underlying.items()
            },
            by_sector={
                key: round(value, 6) for key, value in by_sector.items()
            },
            by_strategy={
                key: round(value, 6) for key, value in by_strategy.items()
            },
            created_at=now.isoformat(),
        )
