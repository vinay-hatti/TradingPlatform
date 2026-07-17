from __future__ import annotations

from trading_ai.daily.models import DailyCandidate
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
    ):
        self.market_service = market_service
        self.feature_pipeline = feature_pipeline
        self.live_profile = live_profile
        self.min_score = float(min_score)
        self.pricing_dte = int(pricing_dte)
        self.start = start
        self.end = end

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
            expiry=f"{self.pricing_dte}DTE_PROXY",
            option_price=float(option_price),
            delta=float(greeks["delta"]),
            gamma=float(greeks["gamma"]),
            theta=float(greeks["theta"]),
            vega=float(greeks["vega"]),
            rho=float(greeks["rho"]),
            volatility=float(greeks["volatility"]),
            dte=int(greeks["dte"]),
            final_score=float(legacy_score),
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
