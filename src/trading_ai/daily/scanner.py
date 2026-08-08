from __future__ import annotations
from datetime import date, timedelta
import math
from trading_ai.options.live_contract_selector import (
    LiveContractSelectionPolicy,
    LiveOptionContractSelector,
)
from trading_ai.options.live_snapshot import LiveOptionDataError
from trading_ai.options.repository_snapshot_provider import RepositoryOptionSnapshotProvider

from trading_ai.daily.models import DailyCandidate
from trading_ai.daily.expiry_selector import StandardFridayExpirySelector
from trading_ai.daily.sectors import sector_for
from trading_ai.daily.strike_selector import TargetDeltaStrikeSelector
from trading_ai.options.pricing_service import OptionPricingService
from trading_ai.portfolio.awareness import PortfolioAwareness
from trading_ai.ranking.ai_score import AITradeRanker
from trading_ai.institutional_market_structure import scanner_context
from trading_ai.institutional_market_structure.scanner_repository import DealerPositioningScannerRepository
from trading_ai.trend_intelligence.repository import TrendIntelligenceRepository
from trading_ai.trend_intelligence.transition_repository import TrendTransitionRepository
from trading_ai.trend_intelligence.forecast_repository import TrendForecastRepository
from trading_ai.trend_intelligence.institutional_repository import InstitutionalTrendRepository
from trading_ai.stock_intelligence.option_integration import (
    UnderlyingOptionIntegrationPolicy,
    UnderlyingOptionIntegrationService,
)


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
        expiration_mode="automatic",
        minimum_dte=14,
        maximum_dte=90,
        maximum_expirations_per_symbol=4,
        maximum_trades_per_expiration=3,
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
        enable_dealer_positioning=True,
        dealer_positioning_repository=None,
        maximum_dealer_snapshot_age_days=1,
        dealer_positioning_weight=1.0,
        maximum_dealer_score_adjustment=15.0,
        published_state_context=None,
        option_snapshot_as_of=None,
        enable_trend_intelligence=True,
        trend_intelligence_repository=None,
        maximum_trend_snapshot_age_days=3,
        trend_intelligence_weight=1.0,
        maximum_trend_score_adjustment=6.0,
        enable_trend_transition_intelligence=True,
        trend_transition_repository=None,
        maximum_transition_snapshot_age_days=3,
        transition_intelligence_weight=1.0,
        maximum_transition_score_adjustment=2.0,
        enable_trend_forecast_intelligence=True,
        trend_forecast_repository=None,
        forecast_horizon_days=10,
        maximum_forecast_snapshot_age_days=3,
        forecast_intelligence_weight=1.0,
        maximum_forecast_score_adjustment=2.0,
        enable_institutional_trend_intelligence=True,
        institutional_trend_repository=None,
        maximum_institutional_snapshot_age_days=3,
        institutional_intelligence_weight=1.0,
        maximum_institutional_score_adjustment=2.0,
        enable_stock_intelligence_integration=False,
        stock_intelligence_provider=None,
        stock_intelligence_policy=None,
    ):
        self.market_service = market_service
        self.feature_pipeline = feature_pipeline
        self.live_profile = live_profile
        self.min_score = float(min_score)
        self.pricing_dte = int(pricing_dte)
        self.expiration_mode = str(expiration_mode).lower()
        self.minimum_dte = int(minimum_dte)
        self.maximum_dte = int(maximum_dte)
        self.maximum_expirations_per_symbol = int(maximum_expirations_per_symbol)
        self.maximum_trades_per_expiration = int(maximum_trades_per_expiration)
        if self.minimum_dte <= 0 or self.minimum_dte > self.maximum_dte:
            raise ValueError("invalid DTE range")
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

        self.option_snapshot_as_of = (
            date.fromisoformat(str(option_snapshot_as_of)[:10])
            if option_snapshot_as_of
            else date.fromisoformat(str(end)[:10])
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
                provider=RepositoryOptionSnapshotProvider(snapshot_as_of=self.option_snapshot_as_of),
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
        self.enable_dealer_positioning = bool(enable_dealer_positioning)
        self.dealer_positioning_repository = (
            dealer_positioning_repository or DealerPositioningScannerRepository()
        )
        self.maximum_dealer_snapshot_age_days = int(maximum_dealer_snapshot_age_days)
        self.dealer_positioning_weight = max(0.0, float(dealer_positioning_weight))
        self.maximum_dealer_score_adjustment = max(0.0, float(maximum_dealer_score_adjustment))
        self.published_state_context = published_state_context
        self.enable_trend_intelligence = bool(enable_trend_intelligence)
        self.trend_intelligence_repository = trend_intelligence_repository or TrendIntelligenceRepository()
        self.maximum_trend_snapshot_age_days = int(maximum_trend_snapshot_age_days)
        self.trend_intelligence_weight = max(0.0, float(trend_intelligence_weight))
        self.maximum_trend_score_adjustment = max(0.0, float(maximum_trend_score_adjustment))
        self.enable_trend_transition_intelligence = bool(enable_trend_transition_intelligence)
        self.trend_transition_repository = trend_transition_repository or TrendTransitionRepository()
        self.maximum_transition_snapshot_age_days = int(maximum_transition_snapshot_age_days)
        self.transition_intelligence_weight = max(0.0, float(transition_intelligence_weight))
        self.maximum_transition_score_adjustment = max(0.0, float(maximum_transition_score_adjustment))
        self.enable_trend_forecast_intelligence = bool(enable_trend_forecast_intelligence)
        self.trend_forecast_repository = trend_forecast_repository or TrendForecastRepository()
        self.forecast_horizon_days = int(forecast_horizon_days)
        self.maximum_forecast_snapshot_age_days = int(maximum_forecast_snapshot_age_days)
        self.forecast_intelligence_weight = max(0.0, float(forecast_intelligence_weight))
        self.maximum_forecast_score_adjustment = max(0.0, float(maximum_forecast_score_adjustment))
        self.enable_institutional_trend_intelligence = bool(enable_institutional_trend_intelligence)
        self.institutional_trend_repository = institutional_trend_repository or InstitutionalTrendRepository()
        self.maximum_institutional_snapshot_age_days = int(maximum_institutional_snapshot_age_days)
        self.institutional_intelligence_weight = max(0.0, float(institutional_intelligence_weight))
        self.maximum_institutional_score_adjustment = max(0.0, float(maximum_institutional_score_adjustment))
        self.enable_stock_intelligence_integration = bool(enable_stock_intelligence_integration)
        self.stock_intelligence_provider = stock_intelligence_provider
        if stock_intelligence_policy is None:
            stock_intelligence_policy = UnderlyingOptionIntegrationPolicy(
                enabled=self.enable_stock_intelligence_integration
            )
        self.stock_intelligence_integration = UnderlyingOptionIntegrationService(
            stock_intelligence_policy
        )

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

    def _target_dtes(self):
        presets = {
            "short": (7, 21), "swing": (22, 45),
            "medium": (46, 75), "long": (76, 120),
        }
        if self.expiration_mode == "fixed":
            return [self.pricing_dte]
        lo, hi = presets.get(self.expiration_mode, (self.minimum_dte, self.maximum_dte))
        lo, hi = max(lo, self.minimum_dte), min(hi, self.maximum_dte)
        if lo > hi:
            lo, hi = self.minimum_dte, self.maximum_dte
        count = max(1, self.maximum_expirations_per_symbol)
        if count == 1 or lo == hi:
            return [round((lo + hi) / 2)]
        return sorted(set(round(lo + i * (hi - lo) / (count - 1)) for i in range(count)))

    def _select_live_across_horizons(self, *, symbol, signal, close, hv20):
        ranked = []
        errors = []
        as_of = self.option_snapshot_as_of
        for target_dte in self._target_dtes():
            strike_selection = self.strike_selector.select(
                signal=signal, spot=close, volatility=hv20, dte=target_dte
            )
            try:
                live = self.live_selector.select(
                    underlying=symbol, signal=signal,
                    target_expiration=as_of + timedelta(days=target_dte),
                    target_strike=float(strike_selection.strike), as_of=as_of,
                )
                theta_efficiency = max(0.0, 100.0 - abs(float(live.theta)) * 1000.0)
                horizon_score = live.score.total_score * 0.90 + theta_efficiency * 0.10
                ranked.append((horizon_score, live, strike_selection, target_dte))
            except LiveOptionDataError as exc:
                errors.append(str(exc))
        if not ranked:
            raise LiveOptionDataError("No eligible contracts across configured DTE horizons. " + " | ".join(errors[-3:]))
        return max(ranked, key=lambda item: (item[0], item[1].score.liquidity_score))

    @staticmethod
    def _resolve_candidate_expiry(*, symbol, as_of, selected_live_contract, option_data_source, expiry_selector, valuation_date, proxy_dte):
        if selected_live_contract is not None:
            contract_ticker = str(selected_live_contract.contract_ticker or "").strip()
            candidate_expiry = str(selected_live_contract.expiration_date)
            try:
                expiration_date = date.fromisoformat(candidate_expiry[:10])
            except ValueError as exc:
                raise LiveOptionDataError(
                    f"Persisted option contract for {symbol} has invalid expiration "
                    f"{candidate_expiry!r}."
                ) from exc

            candidate_dte = (expiration_date - as_of).days
            if candidate_dte <= 0:
                raise LiveOptionDataError(
                    f"Persisted option contract for {symbol} is expired: "
                    f"{candidate_expiry}."
                )
            if not contract_ticker:
                raise LiveOptionDataError(
                    f"Persisted option contract for {symbol} is missing its contract "
                    "ticker. Verify OptionChainRepository contract_ticker mapping."
                )
            if str(option_data_source).upper() not in {
                "POLYGON_PERSISTED",
                "POLYGON",
                "LIVE",
            }:
                raise LiveOptionDataError(
                    f"Selected listed contract for {symbol} has inconsistent data "
                    f"source {option_data_source!r}."
                )
            return (
                contract_ticker,
                candidate_expiry,
                candidate_dte,
                "LIVE_LISTED_CONTRACT",
            )

        expiry_selection = expiry_selector.select(
            valuation_date=valuation_date,
            target_dte=proxy_dte,
        )
        return (
            "",
            expiry_selection.expiration_iso,
            int(expiry_selection.actual_dte),
            expiry_selection.source,
        )

    def _dealer_positioning_context(self, *, symbol, signal, scan_date):
        neutral = {
            "dealer_context_status": "DISABLED" if not self.enable_dealer_positioning else "MISSING",
            "dealer_snapshot_date": "",
            "dealer_snapshot_age_days": -1,
            "institutional_positioning_score": 0.0,
            "positioning_label": "UNAVAILABLE",
            "gamma_regime": "UNAVAILABLE",
            "gamma_flip": None,
            "spot_vs_gamma_flip_pct": None,
            "primary_call_wall": None,
            "primary_put_wall": None,
            "distance_to_call_wall_pct": None,
            "distance_to_put_wall_pct": None,
            "dealer_hedging_pressure": 0.0,
            "range_probability": 0.0,
            "breakout_probability": 0.0,
            "breakdown_probability": 0.0,
            "volatility_expansion_probability": 0.0,
            "market_structure_confidence": 0.0,
            "directional_alignment_probability": 0.0,
            "dealer_score_adjustment": 0.0,
            "dealer_context_warning": "",
        }
        if not self.enable_dealer_positioning:
            return neutral
        result = self.dealer_positioning_repository.load_latest(
            symbol=symbol,
            scan_date=scan_date,
            maximum_age_days=self.maximum_dealer_snapshot_age_days,
        )
        neutral["dealer_context_status"] = result.status
        neutral["dealer_snapshot_age_days"] = result.snapshot_age_days if result.snapshot_age_days is not None else -1
        neutral["dealer_context_warning"] = result.error or ""
        if result.status != "FRESH" or result.snapshot is None:
            return neutral
        snapshot = result.snapshot
        context = scanner_context(snapshot, option_type=signal, strategy_family="LONG_PREMIUM")
        raw_adjustment = float(context.get("scanner_score_adjustment", 0.0) or 0.0)
        weighted_adjustment = raw_adjustment * self.dealer_positioning_weight
        capped_adjustment = max(
            -self.maximum_dealer_score_adjustment,
            min(self.maximum_dealer_score_adjustment, weighted_adjustment),
        )
        call_distance = None if snapshot.primary_call_wall is None else (snapshot.primary_call_wall-snapshot.spot)/snapshot.spot*100
        put_distance = None if snapshot.primary_put_wall is None else (snapshot.primary_put_wall-snapshot.spot)/snapshot.spot*100
        neutral.update({
            "dealer_context_status": "FRESH",
            "dealer_snapshot_date": snapshot.option_snapshot_date,
            "institutional_positioning_score": float(snapshot.institutional_positioning_score),
            "positioning_label": snapshot.positioning_label,
            "gamma_regime": snapshot.gamma_regime,
            "gamma_flip": snapshot.gamma_flip,
            "spot_vs_gamma_flip_pct": snapshot.gamma_flip_distance_pct,
            "primary_call_wall": snapshot.primary_call_wall,
            "primary_put_wall": snapshot.primary_put_wall,
            "distance_to_call_wall_pct": call_distance,
            "distance_to_put_wall_pct": put_distance,
            "dealer_hedging_pressure": float(snapshot.dealer_hedging_pressure),
            "range_probability": float(snapshot.range_probability),
            "breakout_probability": float(snapshot.breakout_probability),
            "breakdown_probability": float(snapshot.breakdown_probability),
            "volatility_expansion_probability": float(snapshot.volatility_expansion_probability),
            "market_structure_confidence": float(snapshot.confidence_score),
            "directional_alignment_probability": float(context.get("directional_alignment_probability", 0.0) or 0.0),
            "dealer_score_adjustment": float(capped_adjustment),
        })
        return neutral

    def _trend_intelligence_context(self, *, symbol, signal):
        neutral = {
            "trend_context_status": "DISABLED" if not self.enable_trend_intelligence else "MISSING",
            "trend_snapshot_date": "", "trend_snapshot_age_days": -1,
            "short_term_trend": "UNAVAILABLE", "intermediate_term_trend": "UNAVAILABLE", "long_term_trend": "UNAVAILABLE",
            "trend_alignment_score": 50.0, "signal_trend_alignment_score": 50.0, "trend_quality_score": 50.0,
            "trend_confidence": 0.0, "trend_stage": "UNAVAILABLE", "trend_age_days": 0,
            "relative_strength_vs_spy": 0.0, "relative_strength_vs_sector": 0.0, "relative_strength_grade": "UNAVAILABLE",
            "sector_trend_alignment_score": 50.0, "market_trend_alignment_score": 50.0,
            "trend_score_adjustment": 0.0, "trend_context_warning": "",
            "trend_sector": "Unknown", "trend_sector_etf": "", "relative_strength_multiplier": 1.0,
        }
        if not self.enable_trend_intelligence:
            return neutral
        try:
            context = self.trend_intelligence_repository.scanner_context(
                symbol, signal, maximum_age_days=self.maximum_trend_snapshot_age_days, reference_date=self.end
            )
        except Exception as exc:
            neutral["trend_context_status"] = "ERROR"
            neutral["trend_context_warning"] = str(exc)
            return neutral
        neutral.update(context)
        raw = float(neutral.get("trend_score_adjustment", 0.0) or 0.0) * self.trend_intelligence_weight
        neutral["trend_score_adjustment"] = max(-self.maximum_trend_score_adjustment, min(self.maximum_trend_score_adjustment, raw))
        return neutral

    def _trend_transition_context(self, *, symbol, signal):
        neutral = {
            "transition_context_status": "DISABLED" if not self.enable_trend_transition_intelligence else "MISSING",
            "transition_snapshot_date": "", "transition_snapshot_age_days": -1,
            "transition_state": "UNAVAILABLE", "transition_direction": "UNAVAILABLE",
            "breakout_state": "UNAVAILABLE", "channel_position_pct": 50.0,
            "momentum_acceleration_score": 0.0, "volatility_state": "UNAVAILABLE",
            "volatility_percentile": 50.0, "reversal_risk_score": 0.0,
            "exhaustion_risk_score": 0.0, "transition_confirmation_score": 50.0,
            "transition_score_adjustment": 0.0, "transition_context_warning": "",
        }
        if not self.enable_trend_transition_intelligence:
            return neutral
        try:
            context = self.trend_transition_repository.scanner_context(
                symbol, signal, maximum_age_days=self.maximum_transition_snapshot_age_days,
                reference_date=self.end,
            )
        except Exception as exc:
            neutral["transition_context_status"] = "ERROR"
            neutral["transition_context_warning"] = str(exc)
            return neutral
        neutral.update(context)
        raw = float(neutral.get("transition_score_adjustment", 0.0) or 0.0) * self.transition_intelligence_weight
        neutral["transition_score_adjustment"] = max(
            -self.maximum_transition_score_adjustment,
            min(self.maximum_transition_score_adjustment, raw),
        )
        return neutral

    def _trend_forecast_context(self, *, symbol, signal):
        neutral = {
            "forecast_context_status": "DISABLED" if not self.enable_trend_forecast_intelligence else "MISSING",
            "forecast_snapshot_date": "", "forecast_snapshot_age_days": -1,
            "forecast_direction": "UNAVAILABLE", "forecast_horizon_days": self.forecast_horizon_days,
            "forecast_requested_horizon_days": self.forecast_horizon_days,
            "forecast_resolved_horizon_days": None,
            "forecast_horizon_distance_days": None,
            "forecast_horizon_resolution": "UNRESOLVED",
            "continuation_probability": 50.0, "reversal_probability": 50.0,
            "forecast_confidence_score": 0.0, "forecast_confidence_grade": "UNAVAILABLE",
            "forecast_expected_return_pct": 0.0, "forecast_expected_volatility_pct": 0.0,
            "forecast_persistence_days": 0, "forecast_score_adjustment": 0.0,
            "forecast_context_warning": "",
        }
        if not self.enable_trend_forecast_intelligence:
            return neutral
        try:
            neutral.update(self.trend_forecast_repository.scanner_context(
                symbol, signal, horizon_days=self.forecast_horizon_days,
                maximum_age_days=self.maximum_forecast_snapshot_age_days, reference_date=self.end,
            ))
        except Exception as exc:
            neutral.update(forecast_context_status="ERROR", forecast_context_warning=str(exc))
            return neutral
        raw = float(neutral.get("forecast_score_adjustment", 0.0) or 0.0) * self.forecast_intelligence_weight
        neutral["forecast_score_adjustment"] = max(-self.maximum_forecast_score_adjustment, min(self.maximum_forecast_score_adjustment, raw))
        return neutral

    def _institutional_trend_context(self, *, symbol):
        neutral = {
            "institutional_context_status": "DISABLED" if not self.enable_institutional_trend_intelligence else "MISSING",
            "institutional_snapshot_date": "", "institutional_snapshot_age_days": -1,
            "participation_score": 50.0, "participation_grade": "UNAVAILABLE", "participation_state": "UNAVAILABLE",
            "leadership_score": 50.0, "leadership_grade": "UNAVAILABLE", "leadership_state": "UNAVAILABLE",
            "institutional_trend_quality_score": 50.0, "institutional_conviction_score": 50.0,
            "deterioration_risk_score": 50.0, "deterioration_state": "UNAVAILABLE",
            "breadth_confirmation_score": 50.0, "cross_asset_confirmation_score": 50.0,
            "institutional_score_adjustment": 0.0, "institutional_context_warning": "",
        }
        if not self.enable_institutional_trend_intelligence:
            return neutral
        try:
            context = dict(self.institutional_trend_repository.scanner_context(
                symbol, maximum_age_days=self.maximum_institutional_snapshot_age_days, reference_date=self.end,
            ))
        except Exception as exc:
            neutral.update(institutional_context_status="ERROR", institutional_context_warning=str(exc))
            return neutral
        if "trend_quality_score" in context:
            context["institutional_trend_quality_score"] = context.pop("trend_quality_score")
        neutral.update(context)
        if neutral.get("institutional_context_status") == "FRESH":
            raw = ((float(neutral["participation_score"])-50.0)+(float(neutral["leadership_score"])-50.0)+(float(neutral["institutional_trend_quality_score"])-50.0)-(float(neutral["deterioration_risk_score"])-50.0))/100.0
            raw *= self.institutional_intelligence_weight
            neutral["institutional_score_adjustment"] = max(-self.maximum_institutional_score_adjustment, min(self.maximum_institutional_score_adjustment, raw))
        return neutral

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

        proxy_dte = self.pricing_dte if self.expiration_mode == "fixed" else round((self.minimum_dte + self.maximum_dte) / 2)
        selection = self.strike_selector.select(signal=signal, spot=close, volatility=hv20, dte=proxy_dte)
        strike = float(selection.strike)
        target_expiration = date.fromisoformat(self.end[:10]) + timedelta(days=proxy_dte)
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
        selected_live_contract = None
        greek_source = "PERSISTED"

        if self.live_selector is not None:
            try:
                _, live, selection, _ = self._select_live_across_horizons(
                    symbol=symbol, signal=signal, close=close, hv20=hv20
                )
                selected_live_contract = live
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
                required = ("delta", "gamma", "theta", "vega")
                invalid_persisted_greeks = any(
                    not math.isfinite(float(greeks[name])) for name in required
                ) or abs(float(greeks["delta"])) < 1e-9
                if invalid_persisted_greeks:
                    fallback = self.pricing.greeks(
                        signal=signal, spot=close, strike=float(live.strike),
                        hv20=hv20, dte=max(int(live.dte), 1),
                    )
                    for name in ("delta", "gamma", "theta", "vega", "rho", "volatility"):
                        greeks[name] = float(fallback[name])
                    greek_source = "BLACK_SCHOLES_FALLBACK"
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
            expiry = f"{proxy_dte}DTE_PROXY"
            option_price = self.pricing.option_price(
                signal=signal,
                spot=close,
                strike=strike,
                hv20=hv20,
                dte=proxy_dte,
            )
            greeks = self.pricing.greeks(
                signal=signal,
                spot=close,
                strike=strike,
                hv20=hv20,
                dte=proxy_dte,
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

        trend_context = self._trend_intelligence_context(symbol=symbol, signal=signal)
        transition_context = self._trend_transition_context(symbol=symbol, signal=signal)
        forecast_context = self._trend_forecast_context(symbol=symbol, signal=signal)
        institutional_context = self._institutional_trend_context(symbol=symbol)
        trend_sector = str(trend_context.get("trend_sector", "") or "").strip()
        sector = trend_sector if trend_sector and trend_sector != "Unknown" else sector_for(symbol)
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

        as_of = date.fromisoformat(self.end[:10])
        dealer_context = self._dealer_positioning_context(
            symbol=symbol, signal=signal, scan_date=self.option_snapshot_as_of
        )
        base_ai_score = float(ranking["ai_score"])
        dealer_adjustment = float(dealer_context["dealer_score_adjustment"])
        base_trend_adjustment = float(trend_context["trend_score_adjustment"])
        transition_adjustment = float(transition_context["transition_score_adjustment"])
        forecast_adjustment = float(forecast_context["forecast_score_adjustment"])
        institutional_adjustment = float(institutional_context["institutional_score_adjustment"])
        combined_trend_adjustment = max(
            -self.maximum_trend_score_adjustment,
            min(self.maximum_trend_score_adjustment, base_trend_adjustment + transition_adjustment + forecast_adjustment + institutional_adjustment),
        )
        trend_context["base_trend_score_adjustment"] = base_trend_adjustment
        trend_context["combined_trend_score_adjustment"] = combined_trend_adjustment
        trend_context["trend_score_adjustment"] = combined_trend_adjustment
        trend_adjustment = combined_trend_adjustment
        raw_ai_score = base_ai_score + dealer_adjustment + combined_trend_adjustment
        final_ai_score = max(0.0, min(100.0, raw_ai_score))
        score_capped = not math.isclose(raw_ai_score, final_ai_score, abs_tol=1e-9)
        (
            resolved_contract_ticker,
            candidate_expiry,
            candidate_dte,
            candidate_expiry_source,
        ) = self._resolve_candidate_expiry(
            symbol=symbol,
            as_of=(self.option_snapshot_as_of if selected_live_contract is not None else as_of),
            selected_live_contract=selected_live_contract,
            option_data_source=option_data_source,
            expiry_selector=self.expiry_selector,
            valuation_date=self.end,
            proxy_dte=proxy_dte,
        )
        if selected_live_contract is not None:
            contract_ticker = resolved_contract_ticker
            greeks["dte"] = candidate_dte

        resolved_delta = float(greeks["delta"])
        strike_note = (
            f"Target-delta strike={strike:.2f}; "
            f"spot={close:.2f}; "
            f"target |delta|={selection.target_delta:.2f}; "
            f"resolved delta={resolved_delta:.4f}; "
            f"Greek source={greek_source}; "
            f"moneyness={selection.moneyness_pct:.2%}."
        )
        ranking_reason = (
            f"{ranking['ranking_reason']} | {strike_note} | "
            f"expiration_mode={self.expiration_mode}; selected_dte={candidate_dte}."
        )
        if dealer_context["dealer_context_status"] == "FRESH":
            ranking_reason += (
                f" | Dealer positioning {dealer_context['positioning_label']} "
                f"({dealer_context['gamma_regime']}), adjustment="
                f"{dealer_adjustment:+.2f}, confidence="
                f"{dealer_context['market_structure_confidence']:.2f}."
            )
        elif self.enable_dealer_positioning:
            ranking_reason += (
                f" | Dealer positioning {dealer_context['dealer_context_status']}; "
                "neutral score adjustment."
            )
        if trend_context["trend_context_status"] == "FRESH":
            ranking_reason += (
                f" | Trend {trend_context['long_term_trend']}/"
                f"{trend_context['intermediate_term_trend']}/{trend_context['short_term_trend']}; "
                f"signal alignment={trend_context['signal_trend_alignment_score']:.1f}, "
                f"base adjustment={base_trend_adjustment:+.2f}, total trend adjustment={combined_trend_adjustment:+.2f}, RS={trend_context['relative_strength_grade']}."
            )
        elif self.enable_trend_intelligence:
            ranking_reason += f" | Trend intelligence {trend_context['trend_context_status']}; neutral adjustment."
        if transition_context["transition_context_status"] == "FRESH":
            ranking_reason += (
                f" | Transition {transition_context['transition_state']}/{transition_context['breakout_state']}; "
                f"confirmation={transition_context['transition_confirmation_score']:.1f}, "
                f"reversal risk={transition_context['reversal_risk_score']:.1f}, "
                f"exhaustion risk={transition_context['exhaustion_risk_score']:.1f}, "
                f"adjustment={transition_adjustment:+.2f}."
            )
        elif self.enable_trend_transition_intelligence:
            ranking_reason += f" | Transition intelligence {transition_context['transition_context_status']}; neutral adjustment."
        if forecast_context["forecast_context_status"] in {"FRESH", "FRESH_APPROXIMATE_HORIZON"}:
            requested_horizon = forecast_context.get("forecast_requested_horizon_days", forecast_context.get("forecast_horizon_days"))
            resolved_horizon = forecast_context.get("forecast_resolved_horizon_days", forecast_context.get("forecast_horizon_days"))
            horizon_resolution = forecast_context.get("forecast_horizon_resolution", "EXACT")
            ranking_reason += (
                f" | Forecast {forecast_context['forecast_direction']}; "
                f"confidence={forecast_context['forecast_confidence_score']:.1f}, "
                f"requested horizon={requested_horizon}D, resolved horizon={resolved_horizon}D, "
                f"resolution={horizon_resolution}, adjustment={forecast_adjustment:+.2f}."
            )
        elif self.enable_trend_forecast_intelligence:
            ranking_reason += f" | Forecast intelligence {forecast_context['forecast_context_status']}; neutral adjustment."
        if institutional_context["institutional_context_status"] == "FRESH":
            ranking_reason += f" | Institutional {institutional_context['participation_state']}; participation={institutional_context['participation_score']:.1f}, conviction={institutional_context['institutional_conviction_score']:.1f}, adjustment={institutional_adjustment:+.2f}."
        elif self.enable_institutional_trend_intelligence:
            ranking_reason += f" | Institutional trend intelligence {institutional_context['institutional_context_status']}; neutral adjustment."

        candidate = DailyCandidate(
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
            expiry=candidate_expiry,
            expiry_source=candidate_expiry_source,
            option_price=float(option_price),
            delta=float(greeks["delta"]),
            gamma=float(greeks["gamma"]),
            theta=float(greeks["theta"]),
            vega=float(greeks["vega"]),
            rho=float(greeks["rho"]),
            volatility=float(greeks["volatility"]),
            dte=candidate_dte,
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
            ai_score=float(final_ai_score),
            base_ai_score=float(base_ai_score),
            raw_ai_score=float(raw_ai_score),
            score_capped=bool(score_capped),
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
            **dealer_context,
            **trend_context,
            **transition_context,
            **forecast_context,
            **institutional_context,
            **(self.published_state_context.candidate_fields() if self.published_state_context else {}),
        )
        return self._apply_stock_intelligence(candidate)

    def _apply_stock_intelligence(self, candidate: DailyCandidate) -> DailyCandidate:
        if not self.enable_stock_intelligence_integration:
            return candidate

        payload = None
        if self.stock_intelligence_provider is not None:
            try:
                payload = self.stock_intelligence_provider.get(candidate.symbol)
            except Exception as exc:
                candidate.stock_intelligence_status = "ERROR"
                candidate.stock_intelligence_allowed = False
                candidate.stock_intelligence_rejection_reasons = [
                    f"STOCK_INTELLIGENCE_PROVIDER_ERROR: {type(exc).__name__}: {exc}"
                ]
                return candidate

        raw_probability = float(candidate.directional_alignment_probability or 0.0) / 100.0
        if raw_probability <= 0:
            raw_probability = max(0.01, min(0.99, 0.50 + (candidate.ai_score - 50.0) / 500.0))

        profile = self.stock_intelligence_integration.evaluate(
            symbol=candidate.symbol,
            signal=candidate.signal,
            raw_probability=raw_probability,
            option_volatility=candidate.volatility,
            option_liquidity_score=candidate.liquidity_score,
            option_contract_identity=candidate.contract_ticker,
            stock_payload=payload,
        )
        candidate.stock_intelligence_status = "AVAILABLE" if profile.available else "UNAVAILABLE"
        candidate.stock_intelligence_allowed = profile.allowed
        candidate.raw_option_probability = profile.raw_probability
        candidate.underlying_probability_adjustment = profile.probability_adjustment
        candidate.underlying_adjusted_probability = profile.adjusted_probability
        candidate.underlying_score = profile.underlying_score
        candidate.underlying_confidence = profile.underlying_confidence
        candidate.underlying_management_quality = profile.management_quality
        candidate.underlying_structural_reward_risk = profile.structural_reward_risk
        candidate.underlying_edge_score = profile.edge_score
        candidate.recommended_option_strategy = profile.recommended_strategy
        candidate.underlying_entry_zone_low = profile.recommended_entry_low
        candidate.underlying_entry_zone_high = profile.recommended_entry_high
        candidate.underlying_stop = profile.underlying_stop
        candidate.underlying_targets = list(profile.underlying_targets)
        candidate.underlying_trailing_method = profile.trailing_method
        candidate.underlying_primary_category = profile.primary_category
        candidate.underlying_primary_timeframe = profile.primary_timeframe
        candidate.stock_intelligence_state_hash = profile.state_hash
        candidate.stock_intelligence_warnings = list(profile.warnings)
        candidate.stock_intelligence_rejection_reasons = list(profile.rejection_reasons)
        candidate.stock_intelligence_evidence = list(profile.evidence)
        candidate.ranking_reason += (
            f" | Stock Intelligence score={profile.underlying_score:.1f}, "
            f"adjusted POP={profile.adjusted_probability:.1%}, "
            f"edge={profile.edge_score:.1f}, strategy={profile.recommended_strategy}, "
            f"allowed={profile.allowed}."
        )
        if profile.available:
            candidate.ai_score = max(0.0, min(100.0, (candidate.ai_score * 0.75) + (profile.edge_score * 0.25)))
        return candidate

    @staticmethod
    def _scan_failure_category(exc: Exception) -> str:
        message = str(exc).lower()
        if any(token in message for token in ("429", "too many requests", "rate limit", "ratelimit")):
            return "PROVIDER_RATE_LIMIT"
        if "cached market data" in message or "run ingest-market" in message or "cache" in message and "cover" in message:
            return "CACHE_COVERAGE"
        if "no price data" in message or "no data" in message or "possibly delisted" in message:
            return "NO_DATA"
        if "timeout" in message or "connection" in message:
            return "TRANSIENT_PROVIDER"
        return "OTHER"

    def scan(self, symbols):
        candidates = []
        failures = {}

        for symbol in symbols:
            try:
                candidate = self.scan_symbol(symbol)
                if candidate is not None:
                    if (
                        self.enable_stock_intelligence_integration
                        and not candidate.stock_intelligence_allowed
                    ):
                        category = "STOCK_INTELLIGENCE_REJECTED"
                        bucket = failures.setdefault(category, {"symbols": [], "example": ""})
                        bucket["symbols"].append(symbol)
                        if not bucket["example"]:
                            reasons = ", ".join(candidate.stock_intelligence_rejection_reasons)
                            bucket["example"] = reasons or "Stock Intelligence eligibility rejected"
                        continue
                    candidates.append(candidate)
            except Exception as exc:
                category = self._scan_failure_category(exc)
                bucket = failures.setdefault(category, {"symbols": [], "example": ""})
                bucket["symbols"].append(symbol)
                if not bucket["example"]:
                    bucket["example"] = f"{type(exc).__name__}: {exc}"

        if failures:
            total = sum(len(value["symbols"]) for value in failures.values())
            print("-------------------------------------------")
            print("Scan Exclusion Summary")
            print("-------------------------------------------")
            print(f"Scan Skipped Symbols             {total:>10}")
            for category, value in sorted(failures.items()):
                symbols_for_category = value["symbols"]
                preview = ",".join(symbols_for_category[:20])
                print(f"Scan {category.replace('_', ' ').title():<25} {len(symbols_for_category):>10}")
                print(f"  Symbols: {preview}{' ...' if len(symbols_for_category) > 20 else ''}")
                print(f"  Example: {value['example'][:500]}")

        ranked = sorted(candidates, key=lambda candidate: candidate.ai_score, reverse=True)
        if self.maximum_trades_per_expiration <= 0:
            return ranked
        diversified = []
        counts = {}
        for candidate in ranked:
            expiry = candidate.expiry
            if counts.get(expiry, 0) >= self.maximum_trades_per_expiration:
                continue
            diversified.append(candidate)
            counts[expiry] = counts.get(expiry, 0) + 1
        return diversified
