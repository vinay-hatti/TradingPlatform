from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import text

from trading_ai.database import SessionLocal
from trading_ai.ui.models.option_chain import (
    LiquidityLadderRow,
    OptionChainContract,
    OptionChainQuery,
    OptionChainSnapshot,
    VolatilitySmilePoint,
)


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _normal_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2.0 * math.pi)


def _black_scholes_greeks(
    spot: float,
    strike: float,
    years: float,
    rate: float,
    volatility: float,
    option_type: str,
) -> tuple[float, float, float, float]:
    if min(spot, strike, years, volatility) <= 0:
        return 0.0, 0.0, 0.0, 0.0
    sqrt_t = math.sqrt(years)
    d1 = (
        math.log(spot / strike)
        + (rate + 0.5 * volatility * volatility) * years
    ) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t
    discount = math.exp(-rate * years)

    if option_type == "CALL":
        delta = _normal_cdf(d1)
        theta = (
            -(spot * _normal_pdf(d1) * volatility) / (2.0 * sqrt_t)
            - rate * strike * discount * _normal_cdf(d2)
        ) / 365.0
    else:
        delta = _normal_cdf(d1) - 1.0
        theta = (
            -(spot * _normal_pdf(d1) * volatility) / (2.0 * sqrt_t)
            + rate * strike * discount * _normal_cdf(-d2)
        ) / 365.0

    gamma = _normal_pdf(d1) / (spot * volatility * sqrt_t)
    vega = spot * _normal_pdf(d1) * sqrt_t / 100.0
    return delta, gamma, theta, vega


class InstitutionalOptionChainService:
    def __init__(self, session_factory=SessionLocal) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _f(value: Any, default: float = 0.0) -> float:
        try:
            result = float(value)
            return result if math.isfinite(result) else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _i(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    def expirations(self, symbol: str, quote_date: date | None = None) -> list[date]:
        where = ["upper(underlying_symbol) = :symbol"]
        params: dict[str, Any] = {"symbol": symbol.upper()}
        if quote_date:
            where.append("quote_date = :quote_date")
            params["quote_date"] = quote_date
        sql = text(
            "SELECT DISTINCT expiry FROM option_contract_history "
            f"WHERE {' AND '.join(where)} ORDER BY expiry"
        )
        with self.session_factory() as session:
            return [row[0] for row in session.execute(sql, params).all()]

    def _latest_quote_date(self, session, symbol: str) -> date:
        value = session.execute(
            text(
                "SELECT max(quote_date) FROM option_contract_history "
                "WHERE upper(underlying_symbol) = :symbol"
            ),
            {"symbol": symbol.upper()},
        ).scalar_one_or_none()
        if value is None:
            raise LookupError(f"No stored option-chain data found for {symbol}")
        return value

    def _underlying_price(self, session, symbol: str, quote_date: date) -> float:
        value = session.execute(
            text(
                "SELECT close FROM price_history "
                "WHERE upper(symbol) = :symbol AND date <= :quote_date "
                "ORDER BY date DESC LIMIT 1"
            ),
            {"symbol": symbol.upper(), "quote_date": quote_date},
        ).scalar_one_or_none()
        if value is None:
            raise LookupError(
                f"No underlying price found for {symbol} on or before {quote_date}"
            )
        return float(value)

    def snapshot(self, query: OptionChainQuery) -> OptionChainSnapshot:
        symbol = query.symbol.upper().strip()
        with self.session_factory() as session:
            quote_date = query.quote_date or self._latest_quote_date(session, symbol)
            expirations = self.expirations(symbol, quote_date)
            if not expirations:
                raise LookupError(f"No expirations found for {symbol}")
            expiration = query.expiration or next(
                (item for item in expirations if item >= quote_date),
                expirations[-1],
            )
            spot = self._underlying_price(session, symbol, quote_date)

            where = [
                "upper(underlying_symbol) = :symbol",
                "quote_date = :quote_date",
                "expiry = :expiration",
            ]
            params: dict[str, Any] = {
                "symbol": symbol,
                "quote_date": quote_date,
                "expiration": expiration,
                "limit": query.limit,
            }
            if query.option_type != "ALL":
                where.append("upper(option_type) = :option_type")
                params["option_type"] = query.option_type
            if query.min_strike is not None:
                where.append("strike >= :min_strike")
                params["min_strike"] = query.min_strike
            if query.max_strike is not None:
                where.append("strike <= :max_strike")
                params["max_strike"] = query.max_strike
            where.extend(
                (
                    "coalesce(volume, 0) >= :min_volume",
                    "coalesce(open_interest, 0) >= :min_open_interest",
                )
            )
            params["min_volume"] = query.min_volume
            params["min_open_interest"] = query.min_open_interest

            rows = session.execute(
                text(
                    "SELECT underlying_symbol, expiry, quote_date, strike, "
                    "option_type, bid, ask, last, volume, open_interest, "
                    "implied_volatility, delta, gamma, theta, vega "
                    "FROM option_contract_history "
                    f"WHERE {' AND '.join(where)} "
                    "ORDER BY strike, option_type LIMIT :limit"
                ),
                params,
            ).mappings().all()

        contracts: list[OptionChainContract] = []
        dte = max(0, (expiration - quote_date).days)
        years = max(dte / 365.0, 1.0 / 365.0)
        for row in rows:
            option_type = str(row["option_type"]).upper()
            if option_type in {"C", "CALLS"}:
                option_type = "CALL"
            if option_type in {"P", "PUTS"}:
                option_type = "PUT"
            if option_type not in {"CALL", "PUT"}:
                continue

            bid = max(0.0, self._f(row["bid"]))
            ask = max(0.0, self._f(row["ask"]))
            last = max(0.0, self._f(row["last"]))
            mid = (bid + ask) / 2.0 if ask > 0 else last
            spread = max(0.0, ask - bid)
            spread_pct = spread / mid if mid > 0 else 999.0
            if spread_pct > query.max_spread_pct:
                continue

            strike = self._f(row["strike"])
            iv = max(0.0001, self._f(row["implied_volatility"], 0.20))
            if iv > 5:
                iv /= 100.0

            provider_values = [
                self._f(row["delta"], float("nan")),
                self._f(row["gamma"], float("nan")),
                self._f(row["theta"], float("nan")),
                self._f(row["vega"], float("nan")),
            ]
            calculated = _black_scholes_greeks(
                spot, strike, years, query.risk_free_rate, iv, option_type
            )
            resolved = []
            provider_count = 0
            for provider, fallback in zip(provider_values, calculated):
                if math.isfinite(provider) and provider != 0:
                    resolved.append(provider)
                    provider_count += 1
                else:
                    resolved.append(fallback)
            greek_source = (
                "PROVIDER" if provider_count == 4
                else "CALCULATED" if provider_count == 0
                else "MIXED"
            )

            intrinsic = (
                max(0.0, spot - strike)
                if option_type == "CALL"
                else max(0.0, strike - spot)
            )
            volume = self._i(row["volume"])
            oi = self._i(row["open_interest"])
            liquidity_score = max(
                0.0,
                min(
                    100.0,
                    35.0 * min(1.0, volume / 500.0)
                    + 35.0 * min(1.0, oi / 2000.0)
                    + 30.0 * max(0.0, 1.0 - min(spread_pct, 1.0)),
                ),
            )
            quality = (
                "GOOD" if liquidity_score >= 70
                else "FAIR" if liquidity_score >= 40
                else "POOR"
            )
            contracts.append(
                OptionChainContract(
                    contract_key=(
                        f"{symbol}:{expiration.isoformat()}:{option_type}:{strike:.4f}"
                    ),
                    underlying_symbol=symbol,
                    quote_date=quote_date,
                    expiration=expiration,
                    days_to_expiration=dte,
                    option_type=option_type,
                    strike=strike,
                    bid=bid,
                    ask=ask,
                    last=last,
                    mid=mid,
                    spread=spread,
                    spread_pct=spread_pct,
                    volume=volume,
                    open_interest=oi,
                    implied_volatility=iv,
                    delta=resolved[0],
                    gamma=resolved[1],
                    theta=resolved[2],
                    vega=resolved[3],
                    intrinsic_value=intrinsic,
                    extrinsic_value=max(0.0, mid - intrinsic),
                    moneyness_pct=(strike / spot - 1.0) * 100.0,
                    liquidity_score=liquidity_score,
                    quote_quality=quality,
                    greek_source=greek_source,
                )
            )

        by_strike: dict[float, dict[str, OptionChainContract]] = {}
        for item in contracts:
            by_strike.setdefault(item.strike, {})[item.option_type] = item

        smile = []
        ladder = []
        for strike in sorted(by_strike):
            call = by_strike[strike].get("CALL")
            put = by_strike[strike].get("PUT")
            smile.append(
                VolatilitySmilePoint(
                    strike=strike,
                    call_iv=call.implied_volatility if call else None,
                    put_iv=put.implied_volatility if put else None,
                    call_volume=call.volume if call else 0,
                    put_volume=put.volume if put else 0,
                    call_open_interest=call.open_interest if call else 0,
                    put_open_interest=put.open_interest if put else 0,
                )
            )
            ladder.append(
                LiquidityLadderRow(
                    strike=strike,
                    call_bid=call.bid if call else None,
                    call_ask=call.ask if call else None,
                    call_volume=call.volume if call else 0,
                    call_open_interest=call.open_interest if call else 0,
                    put_bid=put.bid if put else None,
                    put_ask=put.ask if put else None,
                    put_volume=put.volume if put else 0,
                    put_open_interest=put.open_interest if put else 0,
                )
            )

        call_volume = sum(i.volume for i in contracts if i.option_type == "CALL")
        put_volume = sum(i.volume for i in contracts if i.option_type == "PUT")
        call_oi = sum(i.open_interest for i in contracts if i.option_type == "CALL")
        put_oi = sum(i.open_interest for i in contracts if i.option_type == "PUT")

        return OptionChainSnapshot(
            symbol=symbol,
            quote_date=quote_date,
            expiration=expiration,
            underlying_price=spot,
            generated_at=datetime.now(timezone.utc),
            expirations=expirations,
            contracts=contracts,
            volatility_smile=smile,
            liquidity_ladder=ladder,
            put_call_volume_ratio=put_volume / call_volume if call_volume else None,
            put_call_open_interest_ratio=put_oi / call_oi if call_oi else None,
            total_call_volume=call_volume,
            total_put_volume=put_volume,
            total_call_open_interest=call_oi,
            total_put_open_interest=put_oi,
            data_source="option_contract_history",
            delayed=True,
        )
