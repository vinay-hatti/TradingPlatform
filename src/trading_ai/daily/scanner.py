from __future__ import annotations
from datetime import date, timedelta
from trading_ai.options.live_contract_selector import (
    LiveContractSelectionPolicy,
    LiveOptionContractSelector,
)
from trading_ai.options.live_snapshot import LiveOptionDataError

from trading_ai.daily.models import DailyCandidate
from trading_ai.daily.expiry_selector import StandardFridayExpirySelector
from trading_ai.daily.sectors import sector_for
from trading_ai.daily.strike_selector import TargetDeltaStrikeSelector
from trading_ai.options.pricing_service import OptionPricingService
from trading_ai.portfolio.awareness import PortfolioAwareness
from trading_ai.ranking.ai_score import AITradeRanker


class DailyScanner:
    def __init__(
        self,
        market_service,
        feature_pipeline,
        live_profile,
        pricing_service=None,
        portfolio_awareness=None,
        ranker=None,
        strike_selector=None,
        min_score=60.0,
        pricing_dte=30,
        start="2026-01-01",
        end="2026-06-01",
        target_delta=None,
        minimum_otm_pct=None,
        maximum_otm_pct=None,
        option_data_mode="live",
        maximum_option_spread_pct=0.25,
        minimum_option_open_interest=100,
        minimum_option_volume=10,
        delta_weight=0.25,
        expiration_weight=0.15,
        strike_weight=0.10,
        spread_weight=0.15,
        open_interest_weight=0.20,
        volume_weight=0.15,
        liquidity_data_mode="adaptive",
    ):
        self.market_service = market_service
        self.feature_pipeline = feature_pipeline
        self.live_profile = live_profile
        self.min_score = float(min_score)
        self.pricing_dte = int(pricing_dte)
        self.start = start
        self.end = end
        self.option_data_mode = str(option_data_mode).lower()
        if self.option_data_mode not in {"live", "auto", "proxy"}:
            raise ValueError("option_data_mode must be live, auto, or proxy")

        self.expiry_selector = StandardFridayExpirySelector()
        self.pricing = pricing_service or OptionPricingService(
            risk_free_rate=float(
                live_profile.get("risk_free_rate", 0.04)
            ),
            default_dte=self.pricing_dte,
        )

        configured_target_delta = (
            target_delta
            if target_delta is not None
            else live_profile.get("target_delta", 0.45)
        )
        configured_minimum_otm = (
            minimum_otm_pct
            if minimum_otm_pct is not None
            else live_profile.get("minimum_otm_pct", 0.005)
        )
        configured_maximum_otm = (
            maximum_otm_pct
            if maximum_otm_pct is not None
            else live_profile.get("maximum_otm_pct", 0.20)
        )

        self.live_selector = None
        if self.option_data_mode in {"live", "auto"}:
            self.live_selector = LiveOptionContractSelector(
                policy=LiveContractSelectionPolicy(
                    target_abs_delta=float(configured_target_delta),
                    maximum_spread_pct=float(maximum_option_spread_pct),
                    minimum_open_interest=int(minimum_option_open_interest),
                    minimum_volume=int(minimum_option_volume),
                    delta_weight=float(delta_weight),
                    expiration_weight=float(expiration_weight),
                    strike_weight=float(strike_weight),
                    spread_weight=float(spread_weight),
                    open_interest_weight=float(open_interest_weight),
                    volume_weight=float(volume_weight),
                    liquidity_data_mode=str(liquidity_data_mode),
                )
            )
        self.strike_selector = (
            strike_selector
            or TargetDeltaStrikeSelector(
                self.pricing,
                target_delta=float(configured_target_delta),
                minimum_otm_pct=float(configured_minimum_otm),
                maximum_otm_pct=float(configured_maximum_otm),
            )
        )

        self.portfolio = (
            portfolio_awareness or PortfolioAwareness()
        )
        self.ranker = ranker or AITradeRanker()

    def _latest_feature_row(self, symbol):
        df = self.market_service.get_price_history(
            symbol,
            self.start,
            self.end,
        )
        features = self.feature_pipeline.run(df)
        if features is None or len(features) == 0:
            return None
        return features.iloc[-1]

    def _choose_signal(self, row):
        call_score = float(
            row.get("call_score", 0.0) or 0.0
        )
        put_score = float(
            row.get("put_score", 0.0) or 0.0
        )

        if (
            call_score < self.min_score
            and put_score < self.min_score
        ):
            return None, 0.0

        if call_score >= put_score:
            return "CALL", call_score
        return "PUT", put_score

    def _passes_greek_filters(self, greeks):
        abs_delta = abs(float(greeks["delta"]))
        abs_theta = abs(float(greeks["theta"]))
        vega = float(greeks["vega"])

        min_delta = float(
            self.live_profile.get("min_delta", 0.0)
        )
        max_delta = float(
            self.live_profile.get("max_delta", 1.0)
        )
        min_vega = float(
            self.live_profile.get("min_vega", 0.0)
        )
        max_vega = float(
            self.live_profile.get("max_vega", 999.0)
        )
        max_theta = float(
            self.live_profile.get("max_theta", 999.0)
        )

        if abs_delta < min_delta:
            return False
        if abs_delta > max_delta:
            return False
        if vega < min_vega:
            return False
        if vega > max_vega:
            return False
        if abs_theta > max_theta:
            return False
        return True

    def _legacy_final_score(self, signal_score, greeks):
        delta = abs(float(greeks["delta"]))
        vega = float(greeks["vega"])
        theta = abs(float(greeks["theta"]))

        delta_score = max(
            0.0,
            100.0 - abs(delta - 0.55) * 200.0,
        )
        vega_score = max(
            0.0,
            100.0 - abs(vega - 0.25) * 200.0,
        )
        theta_score = max(
            0.0,
            100.0 - theta * 1000.0,
        )

        return (
            signal_score * 0.55
            + delta_score * 0.20
            + vega_score * 0.15
            + theta_score * 0.10
        )

    def scan_symbol(self, symbol):
        row = self._latest_feature_row(symbol)
        if row is None:
            return None

        signal, score = self._choose_signal(row)
        if signal is None:
            return None

        close = float(row.get("close", 0.0) or 0.0)
        if close <= 0:
            return None

        hv20 = float(
            row.get(
                "hv20",
                row.get("iv", 0.30),
            )
            or 0.30
        )

        selection = self.strike_selector.select(
            signal=signal,
            spot=close,
            volatility=hv20,
            dte=self.pricing_dte,
        )
        strike = float(selection.strike)

        target_expiration = (
            date.fromisoformat(self.end[:10])
            + timedelta(days=self.pricing_dte)
        )
        contract_ticker = ""
        bid = ask = last_price = 0.0
        price_source = "BLACK_SCHOLES_PROXY"
        option_data_source = "PROXY"
        quote_timestamp = ""
        open_interest = option_volume = 0
        spread_pct = 0.0
        contract_selection_score = 0.0
        liquidity_score = 0.0
        delta_selection_score = 0.0
        expiration_selection_score = 0.0
        strike_selection_score = 0.0
        spread_selection_score = 0.0
        open_interest_selection_score = 0.0
        volume_selection_score = 0.0
        live_error = None

        if self.live_selector is not None:
            try:
                live = self.live_selector.select(
                    underlying=symbol,
                    signal=signal,
                    target_expiration=target_expiration,
                    target_strike=strike,
                    as_of=date.today(),
                )
                strike = live.strike
                expiry = live.expiration_date
                option_price = live.entry_price
                greeks = {
                    "delta": live.delta,
                    "gamma": live.gamma,
                    "theta": live.theta,
                    "vega": live.vega,
                    "rho": live.rho,
                    "volatility": live.implied_volatility,
                    "dte": live.dte,
                }
                contract_ticker = live.contract_ticker
                bid = live.bid
                ask = live.ask
                last_price = live.last_price
                price_source = live.price_source
                option_data_source = live.data_source
                quote_timestamp = live.quote_timestamp
                open_interest = live.open_interest
                option_volume = live.volume
                spread_pct = live.spread_pct
                contract_selection_score = live.score.total_score
                liquidity_score = live.score.liquidity_score
                delta_selection_score = live.score.delta_score
                expiration_selection_score = live.score.expiration_score
                strike_selection_score = live.score.strike_score
                spread_selection_score = live.score.spread_score
                open_interest_selection_score = live.score.open_interest_score
                volume_selection_score = live.score.volume_score
            except LiveOptionDataError as exc:
                live_error = exc
                if self.option_data_mode == "live":
                    raise

        if self.live_selector is None or live_error is not None:
            expiry = f"{self.pricing_dte}DTE_PROXY"
            option_price = self.pricing.option_price(
                signal=signal,
                spot=close,
                strike=strike,
                hv20=hv20,
                dte=self.pricing_dte,
            )
            greeks = self.pricing.greeks(
                signal=signal,
                spot=close,
                strike=strike,
                hv20=hv20,
                dte=self.pricing_dte,
            )
            if live_error is not None:
                option_data_source = "PROXY_FALLBACK"
                price_source = (
                    "BLACK_SCHOLES_PROXY: " + str(live_error)
                )

        if not self._passes_greek_filters(greeks):
            return None

        legacy_score = self._legacy_final_score(
            score,
            greeks,
        )

        sector = sector_for(symbol)
        portfolio_result = self.portfolio.evaluate(
            symbol=symbol,
            sector=sector,
        )
        adjusted_score = max(
            0.0,
            legacy_score
            - float(portfolio_result["penalty"]),
        )

        ranking = self.ranker.score(
            signal_score=score,
            signal=signal,
            market_regime=str(
                row.get("market_regime", "")
            ),
            delta=greeks["delta"],
            theta=greeks["theta"],
            vega=greeks["vega"],
            volatility=greeks["volatility"],
            portfolio_penalty=portfolio_result["penalty"],
        )

        strike_note = (
            f"Target-delta strike={strike:.2f}; "
            f"spot={close:.2f}; "
            f"target |delta|={selection.target_delta:.2f}; "
            f"estimated delta={selection.estimated_delta:.4f}; "
            f"moneyness={selection.moneyness_pct:.2%}."
        )
        ranking_reason = (
            f"{ranking['ranking_reason']} | {strike_note}"
        )

        expiry_selection = self.expiry_selector.select(
            valuation_date=self.end,
            target_dte=self.pricing_dte,
        )

        return DailyCandidate(
            symbol=symbol,
            signal=signal,
            strategy=(
                "LONG_CALL"
                if signal == "CALL"
                else "LONG_PUT"
            ),
            close=close,
            score=score,
            call_score=float(
                row.get("call_score", 0.0) or 0.0
            ),
            put_score=float(
                row.get("put_score", 0.0) or 0.0
            ),
            market_regime=str(
                row.get("market_regime", "")
            ),
            strike=strike,
            expiry=expiry_selection.expiration_iso,
            expiry_source=expiry_selection.source,
            option_price=float(option_price),
            delta=float(greeks["delta"]),
            gamma=float(greeks["gamma"]),
            theta=float(greeks["theta"]),
            vega=float(greeks["vega"]),
            rho=float(greeks["rho"]),
            volatility=float(greeks["volatility"]),
            dte=int(expiry_selection.actual_dte),
            final_score=float(legacy_score),
            contract_ticker=contract_ticker,
            bid=float(bid),
            ask=float(ask),
            last_price=float(last_price),
            price_source=price_source,
            option_data_source=option_data_source,
            quote_timestamp=quote_timestamp,
            open_interest=int(open_interest),
            option_volume=int(option_volume),
            spread_pct=float(spread_pct),
            contract_selection_score=float(contract_selection_score),
            liquidity_score=float(liquidity_score),
            delta_selection_score=float(delta_selection_score),
            expiration_selection_score=float(expiration_selection_score),
            strike_selection_score=float(strike_selection_score),
            spread_selection_score=float(spread_selection_score),
            open_interest_selection_score=float(open_interest_selection_score),
            volume_selection_score=float(volume_selection_score),
            sector=sector,
            portfolio_penalty=float(
                portfolio_result["penalty"]
            ),
            adjusted_score=float(adjusted_score),
            portfolio_notes=portfolio_result["notes"],
            ai_score=float(ranking["ai_score"]),
            technical_score=float(
                ranking["technical_score"]
            ),
            greeks_score=float(
                ranking["greeks_score"]
            ),
            regime_score=float(
                ranking["regime_score"]
            ),
            volatility_score=float(
                ranking["volatility_score"]
            ),
            risk_score=float(
                ranking["risk_score"]
            ),
            ranking_reason=ranking_reason,
        )

    def scan(self, symbols):
        candidates = []

        for symbol in symbols:
            try:
                candidate = self.scan_symbol(symbol)
                if candidate is not None:
                    candidates.append(candidate)
            except Exception as exc:
                print(f"Skipping {symbol}: {exc}")

        return sorted(
            candidates,
            key=lambda candidate: candidate.ai_score,
            reverse=True,
        )
