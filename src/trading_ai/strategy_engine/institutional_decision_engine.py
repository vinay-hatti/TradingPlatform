import math
from types import SimpleNamespace
from uuid import uuid4
from trading_ai.strategy_engine.probability_service import (
    ProbabilityService,
)
from trading_ai.strategy_engine.probability_calibration_runtime_service import (
    ProbabilityCalibrationRuntimeService,
)
from trading_ai.strategy_engine.probability_calibration_ranking_service import (
    ProbabilityCalibrationRankingService,
)
from trading_ai.strategy_engine.scenario_service import (
    ScenarioService,
)
from trading_ai.strategy_engine.distribution_risk_service import (
    DistributionRiskService,
)
from trading_ai.strategy_engine.risk_surface_service import (
    RiskSurfaceService,
)
from trading_ai.strategy_engine.portfolio_optimization_service import (
    PortfolioOptimizationService,
)
from trading_ai.strategy_engine.portfolio_optimization_frontier_service import (
    PortfolioOptimizationFrontierService,
)
from trading_ai.strategy_engine.portfolio_optimization_recommendation_service import (
    PortfolioOptimizationRecommendationService,
)
from trading_ai.strategy_engine.decision_candidate_bundle import (
    DecisionCandidateBundle,
)
from trading_ai.strategy_engine.decision_policy import (
    DecisionPolicy,
)
from trading_ai.strategy_engine.decision_run_result import (
    DecisionRunResult,
    SymbolDecisionDiagnostic,
)
from trading_ai.strategy_engine.expected_move_engine import (
    ExpectedMoveEngine,
)
from trading_ai.strategy_engine.expiration_optimizer import (
    ExpirationOptimizer,
)
from trading_ai.strategy_engine.greeks_optimizer import (
    GreeksOptimizer,
)
from trading_ai.strategy_engine.institutional_decision import (
    InstitutionalDecision,
)
from trading_ai.strategy_engine.institutional_ranking_engine import (
    InstitutionalRankingEngine,
)
from trading_ai.strategy_engine.liquidity_engine import (
    LiquidityEngine,
)
from trading_ai.strategy_engine.multi_strategy_service import (
    MultiStrategyService,
)
from trading_ai.strategy_engine.opportunity_factory import (
    OpportunityFactory,
)
from trading_ai.strategy_engine.portfolio_risk_limits import (
    PortfolioRiskLimits,
)
from trading_ai.strategy_engine.portfolio_service import (
    PortfolioService,
)
from trading_ai.strategy_engine.strategy_scoring_engine import (
    StrategyScoringEngine,
)
from trading_ai.strategy_engine.strategy_selector import (
    StrategySelector,
)
from trading_ai.strategy_engine.strike_optimizer import (
    StrikeOptimizer,
)
from trading_ai.strategy_engine.walk_forward_integration_service import (
    WalkForwardIntegrationService,
)
from trading_ai.strategy_engine.market_regime_service import MarketRegimeService
from trading_ai.strategy_engine.market_regime_forecast_service import MarketRegimeForecastService
from trading_ai.strategy_engine.market_breadth_service import MarketBreadthService
from trading_ai.strategy_engine.market_regime_integration_service import MarketRegimeIntegrationService
from trading_ai.strategy_engine.execution_integration_service import ExecutionIntegrationService
from trading_ai.strategy_engine.execution_governance_integration_service import ExecutionGovernanceIntegrationService
from trading_ai.strategy_engine.phase10_decision_integration_service import Phase10DecisionIntegrationService
from trading_ai.strategy_engine.volatility_engine import (
    VolatilityEngine,
)


class InstitutionalDecisionEngine:
    """
    Final Milestone 28 orchestration engine.

    The engine is intentionally dependency-injectable so each component
    can be replaced by a test double, broker-aware implementation, or
    future machine-learning implementation.
    """

    def _probability_profile(
        self,
        strategy_candidate,
        strike_candidate,
        payoff_profile,
        volatility_profile,
        expiration_candidate,
    ):
        """Generate Monte Carlo POP and expected-value analytics."""
        structure = getattr(
            strike_candidate,
            "strategy_structure",
            None,
        )

        if structure is None and payoff_profile is not None:
            structure = getattr(
                payoff_profile,
                "strategy_structure",
                None,
            )

        if structure is None:
            return None

        volatility = self._safe_float(
            getattr(
                volatility_profile,
                "current_iv",
                0.0,
            )
            if volatility_profile is not None
            else 0.0
        )

        if volatility <= 0:
            volatility = self._safe_float(
                getattr(
                    strike_candidate,
                    "implied_volatility",
                    0.0,
                )
            )

        if volatility <= 0:
            volatility = self._safe_float(
                getattr(
                    strike_candidate,
                    "iv",
                    0.0,
                )
            )

        dte = int(
            getattr(
                expiration_candidate,
                "dte",
                getattr(
                    strike_candidate,
                    "dte",
                    0,
                ),
            )
            or 0
        )

        if volatility <= 0 or dte <= 0:
            return None

        try:
            return self.probability_service.analyze(
                structure=structure,
                volatility=volatility,
                horizon_days=dte,
                maximum_profit=(
                    getattr(payoff_profile, "maximum_profit", None)
                    if payoff_profile is not None
                    else None
                ),
                maximum_loss=(
                    getattr(payoff_profile, "maximum_loss", None)
                    if payoff_profile is not None
                    else None
                ),
                capital_required=(
                    getattr(payoff_profile, "capital_required", None)
                    if payoff_profile is not None
                    else None
                ),
            )
        except Exception as exc:
            return SimpleNamespace(
                valid=False,
                probability_of_profit=None,
                expected_value=0.0,
                expected_return_on_capital=0.0,
                expected_return_on_risk=0.0,
                probability_of_max_profit=None,
                probability_of_max_loss=None,
                probability_profit_target=None,
                probability_stop_loss=None,
                value_at_risk_95=0.0,
                conditional_value_at_risk_95=0.0,
                simulation_count=0,
                confidence_score=0.0,
                confidence_grade="F",
                method="UNAVAILABLE",
                warnings=[f"Probability analysis failed: {exc}"],
            )

    def _probability_calibration_profile(
        self, raw_probability, *, symbol, strategy, market_regime, direction
    ):
        return self.probability_calibration_runtime_service.calibrate(
            raw_probability, symbol=symbol, strategy=strategy,
            market_regime=market_regime, direction=direction,
        )

    def _scenario_profile(
        self,
        strike_candidate,
        payoff_profile,
        volatility_profile,
        expiration_candidate,
    ):
        """Generate deterministic scenario and stress-test analytics."""
        structure = getattr(
            strike_candidate,
            "strategy_structure",
            None,
        )

        if structure is None and payoff_profile is not None:
            structure = getattr(
                payoff_profile,
                "strategy_structure",
                None,
            )

        if structure is None:
            return None

        volatility = self._safe_float(
            getattr(
                volatility_profile,
                "current_iv",
                0.0,
            )
            if volatility_profile is not None
            else 0.0
        )

        if volatility <= 0:
            volatility = self._safe_float(
                getattr(
                    strike_candidate,
                    "implied_volatility",
                    0.0,
                )
            )

        if volatility <= 0:
            volatility = self._safe_float(
                getattr(
                    strike_candidate,
                    "iv",
                    0.0,
                )
            )

        dte = int(
            getattr(
                expiration_candidate,
                "dte",
                getattr(
                    strike_candidate,
                    "dte",
                    0,
                ),
            )
            or 0
        )

        capital_required = self._profile_value(
            payoff_profile,
            "capital_required",
            self._profile_value(
                strike_candidate,
                "capital_required",
                0.0,
            ),
        )

        maximum_loss = self._profile_value(
            payoff_profile,
            "maximum_loss",
            self._profile_value(
                strike_candidate,
                "max_loss",
                0.0,
            ),
        )

        if volatility <= 0 or dte <= 0:
            return None

        try:
            return self.scenario_service.analyze_strategy(
                structure=structure,
                volatility=volatility,
                days_to_expiry=dte,
                capital_required=capital_required,
                maximum_loss=maximum_loss,
            )
        except Exception as exc:
            return SimpleNamespace(
                valid=False,
                allowed=False,
                stress_score=0.0,
                stress_grade="F",
                risk_severity="UNKNOWN",
                worst_scenario_name="",
                worst_scenario_pnl=0.0,
                maximum_stress_loss=0.0,
                maximum_stress_loss_pct_of_capital=0.0,
                maximum_stress_loss_pct_of_maximum_loss=None,
                rejection_reasons=[
                    "SCENARIO_ANALYSIS_FAILED"
                ],
                warnings=[
                    f"Scenario analysis failed: {exc}"
                ],
            )


    def _distribution_risk_profile(
        self,
        symbol,
        strategy_candidate,
        payoff_profile,
        probability_profile,
        scenario_profile,
        strike_candidate,
        initial_capital=None,
    ):
        """
        Build institutional distribution-risk analytics from the best
        available PnL distribution without changing existing candidate APIs.

        Source precedence:
          1. Candidate historical PnL observations when sufficient.
          2. Monte Carlo PnL observations retained by ProbabilityService.
          3. Scenario/stress PnL observations as a graceful fallback.

        A smaller scenario grid must not replace a richer Monte Carlo sample.
        The account initial capital is passed separately from position capital.
        """

        def finite_values(values):
            if values is None:
                return []

            try:
                raw_values = list(values)
            except TypeError:
                return []

            cleaned = []
            for value in raw_values:
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    continue

                if math.isfinite(numeric):
                    cleaned.append(numeric)

            return cleaned

        historical_values = finite_values(
            getattr(
                strike_candidate,
                "historical_pnl_values",
                None,
            )
        )

        probability_metadata = getattr(
            probability_profile,
            "metadata",
            {},
        ) or {}

        monte_carlo_values = finite_values(
            probability_metadata.get("pnl_values")
            if isinstance(probability_metadata, dict)
            else None
        )

        scenario_values = finite_values(
            getattr(point, "stressed_pnl", None)
            for point in (
                getattr(
                    scenario_profile,
                    "scenario_points",
                    [],
                )
                or []
            )
        )

        minimum_observations = int(
            getattr(
                getattr(
                    self.distribution_risk_service,
                    "policy",
                    None,
                ),
                "minimum_observations",
                2,
            )
            or 2
        )

        if len(historical_values) >= minimum_observations:
            pnl_values = historical_values
            distribution_source = "HISTORICAL_CANDIDATE_PNL"
        elif len(monte_carlo_values) >= minimum_observations:
            pnl_values = monte_carlo_values
            distribution_source = "PROBABILITY_MONTE_CARLO_PNL"
        elif len(historical_values) >= 2:
            pnl_values = historical_values
            distribution_source = "HISTORICAL_CANDIDATE_PNL_LIMITED"
        elif len(monte_carlo_values) >= 2:
            pnl_values = monte_carlo_values
            distribution_source = "PROBABILITY_MONTE_CARLO_PNL_LIMITED"
        else:
            pnl_values = scenario_values
            distribution_source = "SCENARIO_STRESS_PNL"

        capital_required = self._profile_value(
            payoff_profile,
            "capital_required",
            self._profile_value(
                strike_candidate,
                "capital_required",
                self._profile_value(
                    strike_candidate,
                    "max_loss",
                    0.0,
                ),
            ),
        )

        account_capital = self._safe_float(initial_capital)
        if account_capital <= 0:
            account_capital = self._safe_float(capital_required)

        if len(pnl_values) < 2 or capital_required <= 0:
            return None

        try:
            profile = self.distribution_risk_service.analyze_strategy(
                pnl_values=pnl_values,
                capital_required=capital_required,
                symbol=symbol,
                strategy=str(
                    getattr(strategy_candidate, "strategy", "") or ""
                ),
                monte_carlo_pnl_values=(
                    monte_carlo_values or None
                ),
                initial_capital=account_capital,
            )

            metadata = dict(
                getattr(profile, "metadata", {}) or {}
            )
            metadata.update({
                "distribution_source": distribution_source,
                "distribution_observation_count": len(pnl_values),
                "historical_observation_count": len(historical_values),
                "monte_carlo_observation_count": len(monte_carlo_values),
                "scenario_observation_count": len(scenario_values),
                "capital_required": float(capital_required),
                "initial_capital": float(account_capital),
            })
            profile.metadata = metadata
            return profile
        except Exception as exc:
            return SimpleNamespace(
                valid=False,
                allowed=False,
                observation_count=0,
                historical_var=0.0,
                historical_expected_shortfall=0.0,
                parametric_var=0.0,
                parametric_expected_shortfall=0.0,
                historical_var_99=0.0,
                historical_expected_shortfall_99=0.0,
                downside_deviation=0.0,
                skewness=0.0,
                excess_kurtosis=0.0,
                probability_of_large_loss=0.0,
                probability_of_severe_loss=0.0,
                probability_of_critical_loss=0.0,
                drawdown_at_risk=0.0,
                expected_drawdown_shortfall=0.0,
                ulcer_index=0.0,
                pain_index=0.0,
                omega_ratio=None,
                sortino_ratio=None,
                gain_to_pain_ratio=None,
                tail_risk_score=0.0,
                tail_risk_grade="F",
                risk_severity="UNKNOWN",
                rejection_reasons=[
                    "DISTRIBUTION_RISK_ANALYSIS_FAILED"
                ],
                warnings=[
                    f"Distribution-risk analysis failed: {exc}"
                ],
                metadata={
                    "distribution_source": distribution_source,
                    "capital_required": float(capital_required),
                    "initial_capital": float(account_capital),
                },
            )

    def _risk_surface_profile(
        self,
        symbol,
        strategy_candidate,
        underlying_price,
        volatility_profile,
        expiration_candidate,
        greeks_profile,
        payoff_profile,
        strike_candidate,
        initial_capital=None,
    ):
        """Build Phase 4 price/IV/time and Greeks sensitivity surfaces."""
        if greeks_profile is None:
            return None

        implied_volatility = self._safe_float(
            getattr(volatility_profile, "current_iv", 0.0)
            if volatility_profile is not None
            else 0.0
        )
        if implied_volatility <= 0.0:
            implied_volatility = self._safe_float(
                getattr(strike_candidate, "implied_volatility", 0.0)
            )
        if implied_volatility <= 0.0:
            implied_volatility = self._safe_float(
                getattr(strike_candidate, "iv", 0.0)
            )

        days_to_expiration = int(
            getattr(
                expiration_candidate,
                "dte",
                getattr(strike_candidate, "dte", 0),
            )
            or 0
        )
        capital_required = self._profile_value(
            payoff_profile,
            "capital_required",
            self._profile_value(
                strike_candidate,
                "capital_required",
                self._profile_value(strike_candidate, "max_loss", 0.0),
            ),
        )
        account_capital = self._safe_float(initial_capital)
        if account_capital <= 0.0:
            account_capital = self._safe_float(capital_required)

        if (
            self._safe_float(underlying_price) <= 0.0
            or implied_volatility <= 0.0
            or days_to_expiration <= 0
            or account_capital <= 0.0
        ):
            return None

        try:
            return self.risk_surface_service.analyze_strategy(
                symbol=symbol,
                strategy=str(
                    getattr(strategy_candidate, "strategy", "") or ""
                ),
                underlying_price=self._safe_float(underlying_price),
                implied_volatility=implied_volatility,
                days_to_expiration=days_to_expiration,
                capital_required=self._safe_float(capital_required),
                initial_capital=account_capital,
                net_delta=self._safe_float(
                    getattr(greeks_profile, "net_delta", 0.0)
                ),
                net_gamma=self._safe_float(
                    getattr(greeks_profile, "net_gamma", 0.0)
                ),
                net_vega=self._safe_float(
                    getattr(greeks_profile, "net_vega", 0.0)
                ),
                net_theta=self._safe_float(
                    getattr(greeks_profile, "net_theta", 0.0)
                ),
                net_rho=self._safe_float(
                    getattr(greeks_profile, "net_rho", 0.0)
                ),
            )
        except Exception as exc:
            return SimpleNamespace(
                valid=False,
                allowed=False,
                point_count=0,
                worst_case_pnl=0.0,
                best_case_pnl=0.0,
                base_case_pnl=0.0,
                maximum_loss_pct_of_capital=0.0,
                maximum_gain_pct_of_capital=0.0,
                worst_price_shock_pct=0.0,
                worst_volatility_shock=0.0,
                worst_time_offset_days=0,
                delta_gamma_error_estimate=0.0,
                nonlinear_exposure_score=0.0,
                gamma_risk_score=0.0,
                vega_risk_score=0.0,
                theta_risk_score=0.0,
                surface_score=0.0,
                surface_grade="F",
                risk_severity="UNKNOWN",
                rejection_reasons=["RISK_SURFACE_ANALYSIS_FAILED"],
                warnings=[f"Risk-surface analysis failed: {exc}"],
                metadata={"exception_type": type(exc).__name__},
            )

    def __init__(
        self,
        policy: DecisionPolicy | None = None,
        volatility_engine=None,
        expected_move_engine=None,
        strategy_selector=None,
        expiration_optimizer=None,
        strike_optimizer=None,
        greeks_optimizer=None,
        liquidity_engine=None,
        strategy_scoring_engine=None,
        opportunity_factory=None,
        ranking_engine=None,
        multi_strategy_service=None,
        probability_service=None,
        probability_calibration_runtime_service=None,
        probability_calibration_registry=None,
        probability_calibration_registry_path=None,
        probability_calibration_profile=None,
        probability_calibration_ranking_service=None,
        scenario_service=None,
        distribution_risk_service=None,
        risk_surface_service=None,
        portfolio_optimization_service=None,
        portfolio_optimization_frontier_service=None,
        portfolio_optimization_recommendation_service=None,
        apply_portfolio_optimization=False,
        apply_frontier_recommended_policy=False,
        portfolio_service=None,
        portfolio_limits: PortfolioRiskLimits | None = None,
        walk_forward_profile=None,
        walk_forward_calibration_profile=None,
        walk_forward_integration_service=None,
        market_regime_service=None,
        market_regime_forecast_service=None,
        market_breadth_service=None,
        market_regime_integration_service=None,
        execution_integration_service=None,
        execution_fills=None,
        execution_vwap_by_order=None,
        execution_governance_integration_service=None,
        execution_governance_baseline=None,
        execution_governance_current=None,
        execution_governance_profile=None,
        execution_route_registry_profile=None,
        execution_champion_challenger_profile=None,
        execution_governance_baseline_name="BASELINE",
        execution_governance_current_name="CURRENT",
        phase10_decision_integration_service=None,
        adaptive_strategy_profiles=None,
        strategy_learning_profiles=None,
        dynamic_strategy_weighting_profile=None,
        ensemble_decision_profiles=None,
        online_adaptation_profile=None,
        learning_state_registry_profile=None,
        learning_state_promotion_profile=None,
    ):
        self.policy = (
            policy
            or DecisionPolicy()
        )

        self.policy.validate()

        self.volatility_engine = (
            volatility_engine
            or VolatilityEngine()
        )

        self.expected_move_engine = (
            expected_move_engine
            or ExpectedMoveEngine()
        )

        self.strategy_selector = (
            strategy_selector
            or StrategySelector()
        )

        self.expiration_optimizer = (
            expiration_optimizer
            or ExpirationOptimizer()
        )

        self.strike_optimizer = (
            strike_optimizer
            or StrikeOptimizer()
        )

        self.greeks_optimizer = (
            greeks_optimizer
            or GreeksOptimizer()
        )

        self.liquidity_engine = (
            liquidity_engine
            or LiquidityEngine()
        )

        self.strategy_scoring_engine = (
            strategy_scoring_engine
            or StrategyScoringEngine()
        )

        self.opportunity_factory = (
            opportunity_factory
            or OpportunityFactory()
        )

        self.ranking_engine = (
            ranking_engine
            or InstitutionalRankingEngine()
        )

        self.multi_strategy_service = (
            multi_strategy_service
            or MultiStrategyService()
        )

        self.probability_service = (
            probability_service
            or ProbabilityService()
        )

        self.probability_calibration_runtime_service = (
            probability_calibration_runtime_service
            or ProbabilityCalibrationRuntimeService(
                registry=probability_calibration_registry,
                registry_path=probability_calibration_registry_path,
                profile=probability_calibration_profile,
            )
        )

        self.probability_calibration_ranking_service = (
            probability_calibration_ranking_service
            or ProbabilityCalibrationRankingService()
        )

        self.scenario_service = (
            scenario_service
            or ScenarioService()
        )

        self.distribution_risk_service = (
            distribution_risk_service
            or DistributionRiskService()
        )

        self.risk_surface_service = (
            risk_surface_service
            or RiskSurfaceService()
        )

        self.walk_forward_profile = walk_forward_profile
        self.walk_forward_calibration_profile = walk_forward_calibration_profile
        self.walk_forward_integration_service = (
            walk_forward_integration_service
            or WalkForwardIntegrationService()
        )
        self.market_regime_service = market_regime_service or MarketRegimeService()
        self.market_regime_forecast_service = market_regime_forecast_service or MarketRegimeForecastService()
        self.market_breadth_service = market_breadth_service or MarketBreadthService()
        self.market_regime_integration_service = market_regime_integration_service or MarketRegimeIntegrationService()
        self.execution_integration_service = execution_integration_service or ExecutionIntegrationService()
        self.execution_fills = list(execution_fills or [])
        self.execution_vwap_by_order = dict(execution_vwap_by_order or {})
        self.execution_governance_integration_service = (
            execution_governance_integration_service or ExecutionGovernanceIntegrationService()
        )
        self.execution_governance_baseline = list(execution_governance_baseline or [])
        self.execution_governance_current = list(execution_governance_current or [])
        self.execution_governance_profile = execution_governance_profile
        self.execution_route_registry_profile = execution_route_registry_profile
        self.execution_champion_challenger_profile = execution_champion_challenger_profile
        self.execution_governance_baseline_name = str(execution_governance_baseline_name or "BASELINE")
        self.execution_governance_current_name = str(execution_governance_current_name or "CURRENT")
        self.phase10_decision_integration_service = (
            phase10_decision_integration_service or Phase10DecisionIntegrationService()
        )
        self.adaptive_strategy_profiles = adaptive_strategy_profiles or {}
        self.strategy_learning_profiles = strategy_learning_profiles or {}
        self.dynamic_strategy_weighting_profile = dynamic_strategy_weighting_profile
        self.ensemble_decision_profiles = ensemble_decision_profiles or {}
        self.online_adaptation_profile = online_adaptation_profile
        self.learning_state_registry_profile = learning_state_registry_profile
        self.learning_state_promotion_profile = learning_state_promotion_profile

        self.portfolio_optimization_service = (
            portfolio_optimization_service
            or PortfolioOptimizationService()
        )
        self.portfolio_optimization_frontier_service = (
            portfolio_optimization_frontier_service
            or PortfolioOptimizationFrontierService(
                base_policy=self.portfolio_optimization_service.policy
            )
        )
        self.portfolio_optimization_recommendation_service = (
            portfolio_optimization_recommendation_service
            or PortfolioOptimizationRecommendationService()
        )
        self.apply_portfolio_optimization = bool(
            apply_portfolio_optimization
        )
        self.apply_frontier_recommended_policy = bool(
            apply_frontier_recommended_policy
        )

        if portfolio_service is not None:
            self.portfolio_service = (
                portfolio_service
            )
        else:
            limits = (
                portfolio_limits
                or PortfolioRiskLimits()
            )

            self.portfolio_service = (
                PortfolioService(
                    limits=limits
                )
            )

    def analyze_market_regimes(self, request):
        profiles = {}
        forecasts = {}
        history_by_symbol = getattr(request, "price_history_by_symbol", {}) or {}
        for symbol in getattr(request, "symbols", []):
            try:
                profile = self.market_regime_service.analyze(symbol=symbol, price_history=history_by_symbol.get(symbol))
            except TypeError:
                profile = self.market_regime_service.analyze(history_by_symbol.get(symbol), symbol=symbol)
            profiles[symbol] = profile
            try:
                forecasts[symbol] = self.market_regime_forecast_service.forecast_profile(profile)
            except Exception:
                forecasts[symbol] = None
        try:
            breadth = self.market_breadth_service.analyze_portfolio(profiles)
        except Exception:
            breadth = None
        return profiles, forecasts, breadth

    def integrate_market_regime_decision(self, decision, regime_profile=None, forecast_profile=None, breadth_profile=None):
        profile = self.market_regime_integration_service.integrate(
            symbol=decision.symbol, direction=decision.direction, strategy=decision.strategy,
            strategy_score=decision.strategy_score, ranking_score=decision.ranking_score,
            regime_profile=regime_profile, forecast_profile=forecast_profile, breadth_profile=breadth_profile,
        )
        decision.detected_market_regime = profile.current_regime
        decision.forecast_market_regime = profile.forecast_regime
        decision.portfolio_market_regime = profile.portfolio_regime
        decision.market_regime_score = profile.regime_score
        decision.market_regime_confidence = profile.confidence_score
        decision.market_regime_strategy_adjustment = profile.strategy_score_adjustment
        decision.market_regime_ranking_adjustment = profile.ranking_score_adjustment
        decision.market_regime_alignment = profile.strategy_alignment
        decision.market_regime_allowed = profile.allowed
        decision.market_regime_integration_profile = profile
        decision.strategy_score = profile.adapted_strategy_score
        decision.ranking_score = profile.adapted_ranking_score
        decision.warnings.extend(x for x in profile.warnings if x not in decision.warnings)
        decision.rejection_reasons.extend(x for x in profile.rejection_reasons if x not in decision.rejection_reasons)
        if not profile.allowed: decision.allowed = False
        decision.metadata["market_regime_integration_profile"] = profile
        return decision

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def run(
        self,
        request,
    ) -> DecisionRunResult:
        bundles = []
        diagnostics = []
        market_regime_profiles, market_regime_forecast_profiles, market_breadth_profile = self.analyze_market_regimes(request)

        run_warnings = []
        run_errors = []

        for symbol in request.symbols:
            symbol_bundles, diagnostic = (
                self._process_symbol(
                    request=request,
                    symbol=symbol,
                )
            )

            bundles.extend(symbol_bundles)
            diagnostics.append(diagnostic)

            if (
                len(bundles)
                >= self.policy.maximum_total_candidates
            ):
                bundles = bundles[
                    :self.policy.maximum_total_candidates
                ]

                run_warnings.append(
                    "Maximum total candidate limit reached"
                )
                break

        opportunities = [
            bundle.institutional_opportunity
            for bundle in bundles
            if (
                bundle.institutional_opportunity
                is not None
            )
        ]

        ranked = self.ranking_engine.rank(
            opportunities=opportunities,
            include_rejected=(
                request.include_rejected
            ),
        )

        bundle_by_opportunity_id = {
            id(
                bundle.institutional_opportunity
            ): bundle
            for bundle in bundles
            if bundle.institutional_opportunity
            is not None
        }

        for ranked_item in ranked:
            bundle = bundle_by_opportunity_id.get(
                id(ranked_item.opportunity)
            )

            if bundle is not None:
                bundle.ranked_opportunity = (
                    ranked_item
                )

        portfolio_result = None

        if (
            request.construct_portfolio
            and ranked
        ):
            portfolio_result = (
                self.portfolio_service.construct(
                    ranked
                )
            )

            self._attach_portfolio_positions(
                bundles=bundles,
                portfolio_result=portfolio_result,
            )

        decisions = [
            self._build_decision(bundle)
            for bundle in bundles
        ]

        decisions.sort(
            key=lambda decision: (
                decision.selected,
                decision.allowed,
                decision.ranking_score,
                decision.strategy_score,
            ),
            reverse=True,
        )

        portfolio_optimization_profile = (
            self._portfolio_optimization_profile(
                decisions=decisions,
                initial_capital=request.initial_capital,
            )
        )

        portfolio_optimization_frontier_profile = (
            self._portfolio_optimization_frontier_profile(
                decisions=decisions,
                initial_capital=request.initial_capital,
            )
        )
        portfolio_optimization_recommendation = (
            self._portfolio_optimization_recommendation(
                portfolio_optimization_frontier_profile
            )
        )
        if (
            self.apply_frontier_recommended_policy
            and portfolio_optimization_recommendation is not None
            and bool(getattr(portfolio_optimization_recommendation, "valid", False))
            and bool(getattr(portfolio_optimization_recommendation, "allowed", False))
        ):
            recommended_service = PortfolioOptimizationService(
                policy=portfolio_optimization_recommendation.recommended_policy
            )
            portfolio_optimization_profile = recommended_service.optimize(
                candidates=[d for d in decisions if d.allowed],
                initial_capital=float(request.initial_capital or 0.0),
            )

        self._attach_optimization_recommendations(
            decisions=decisions,
            profile=portfolio_optimization_profile,
            apply_selection=self.apply_portfolio_optimization,
        )
        self._attach_frontier_recommendation(
            decisions,
            portfolio_optimization_frontier_profile,
            portfolio_optimization_recommendation,
            self.apply_frontier_recommended_policy,
        )

        walk_forward_integration_profile = (
            self.walk_forward_integration_service.evaluate(
                self.walk_forward_profile,
                source="INSTITUTIONAL_WALK_FORWARD",
            )
        )
        self.walk_forward_integration_service.attach(
            decisions, walk_forward_integration_profile
        )

        for decision in decisions:
            self.integrate_market_regime_decision(decision, market_regime_profiles.get(decision.symbol), market_regime_forecast_profiles.get(decision.symbol), market_breadth_profile)

        execution_integration_profile = self.execution_integration_service.analyze(
            self.execution_fills, vwap_by_order=self.execution_vwap_by_order
        )
        self.execution_integration_service.attach(decisions, execution_integration_profile)

        execution_governance_integration_profile = (
            self.execution_governance_integration_service.analyze(
                baseline_observations=self.execution_governance_baseline,
                current_observations=self.execution_governance_current,
                governance_profile=self.execution_governance_profile,
                route_registry_profile=self.execution_route_registry_profile,
                champion_challenger_profile=self.execution_champion_challenger_profile,
                baseline_name=self.execution_governance_baseline_name,
                current_name=self.execution_governance_current_name,
            )
        )
        self.execution_governance_integration_service.attach(
            decisions, execution_governance_integration_profile
        )

        phase10_decision_integration_profiles = (
            self.phase10_decision_integration_service.analyze(
                decisions,
                adaptive_profiles=self.adaptive_strategy_profiles,
                learning_profiles=self.strategy_learning_profiles,
                dynamic_strategy_weighting_profile=self.dynamic_strategy_weighting_profile,
                ensemble_profiles=self.ensemble_decision_profiles,
                online_adaptation_profile=self.online_adaptation_profile,
                learning_state_registry_profile=self.learning_state_registry_profile,
                learning_state_promotion_profile=self.learning_state_promotion_profile,
            )
        )
        self.phase10_decision_integration_service.attach(
            decisions, phase10_decision_integration_profiles
        )

        selected_decisions = [
            decision
            for decision in decisions
            if decision.selected and decision.allowed
        ]

        portfolio_risk_surface_profile = (
            self._portfolio_risk_surface_profile(
                selected_decisions=selected_decisions,
                initial_capital=request.initial_capital,
            )
        )

        if portfolio_risk_surface_profile is not None:
            for decision in selected_decisions:
                decision.metadata["portfolio_risk_surface_profile"] = (
                    portfolio_risk_surface_profile
                )

        rejected_decisions = [
            decision
            for decision in decisions
            if not decision.allowed
        ]

        processed_symbols = sum(
            1
            for diagnostic in diagnostics
            if diagnostic.processed
        )

        accepted_candidates = sum(
            1
            for bundle in bundles
            if bundle.allowed
        )

        rejected_candidates = (
            len(bundles)
            - accepted_candidates
        )

        valid = bool(
            decisions
        ) and not run_errors

        overall_readiness = (
            self._overall_readiness(
                decisions=decisions,
                portfolio_result=portfolio_result,
            )
        )

        overall_action = (
            self._overall_action(
                decisions=decisions,
                portfolio_result=portfolio_result,
            )
        )

        return DecisionRunResult(
            decisions=decisions,
            selected_decisions=selected_decisions,
            rejected_decisions=rejected_decisions,
            candidate_bundles=bundles,
            ranked_opportunities=ranked,
            portfolio_result=portfolio_result,
            portfolio_risk_surface_profile=portfolio_risk_surface_profile,
            portfolio_optimization_profile=portfolio_optimization_profile,
            portfolio_optimization_frontier_profile=portfolio_optimization_frontier_profile,
            portfolio_optimization_recommendation=portfolio_optimization_recommendation,
            probability_calibration_model_family=(self.probability_calibration_runtime_service.active_family()[0]),
            probability_calibration_model_version=(self.probability_calibration_runtime_service.active_family()[1]),
            walk_forward_profile=walk_forward_integration_profile,
            walk_forward_calibration_profile=self.walk_forward_calibration_profile,
            market_regime_profiles=market_regime_profiles,
            market_regime_forecast_profiles=market_regime_forecast_profiles,
            market_breadth_profile=market_breadth_profile,
            execution_integration_profile=execution_integration_profile,
            execution_aggregation_profile=execution_integration_profile.aggregation_profile,
            execution_benchmark_profile=execution_integration_profile.benchmark_profile,
            execution_routing_profile=execution_integration_profile.routing_profile,
            execution_governance_integration_profile=execution_governance_integration_profile,
            execution_governance_profile=execution_governance_integration_profile.execution_governance_profile,
            execution_route_registry_profile=execution_governance_integration_profile.execution_route_registry_profile,
            execution_champion_challenger_profile=execution_governance_integration_profile.execution_champion_challenger_profile,
            adaptive_strategy_profiles=self.adaptive_strategy_profiles,
            strategy_learning_profiles=self.strategy_learning_profiles,
            dynamic_strategy_weighting_profile=self.dynamic_strategy_weighting_profile,
            ensemble_decision_profiles=self.ensemble_decision_profiles,
            online_adaptation_profile=self.online_adaptation_profile,
            learning_state_registry_profile=self.learning_state_registry_profile,
            learning_state_promotion_profile=self.learning_state_promotion_profile,
            phase10_decision_integration_profiles=phase10_decision_integration_profiles,
            symbol_diagnostics=diagnostics,
            total_symbols=len(
                request.symbols
            ),
            processed_symbols=processed_symbols,
            total_candidates=len(bundles),
            accepted_candidates=accepted_candidates,
            rejected_candidates=rejected_candidates,
            selected_count=len(
                selected_decisions
            ),
            overall_readiness=overall_readiness,
            overall_action=overall_action,
            valid=valid,
            warnings=run_warnings,
            errors=run_errors,
            metadata={
                "request_metadata":
                    dict(request.metadata),
                "ranking_summary":
                    self.ranking_engine.summary(
                        ranked
                    ),
                "portfolio_optimization_applied":
                    self.apply_portfolio_optimization,
                "frontier_recommended_policy_applied":
                    self.apply_frontier_recommended_policy,
                "walk_forward_profile_available":
                    walk_forward_integration_profile.valid,
                "walk_forward_allowed":
                    walk_forward_integration_profile.allowed,
                "execution_profile_available": execution_integration_profile.valid,
                "execution_allowed": execution_integration_profile.allowed,
                "execution_governance_profile_available": execution_governance_integration_profile.governance_available,
                "execution_governance_allowed": execution_governance_integration_profile.allowed,
                "execution_governance_score": execution_governance_integration_profile.governance_score,
                "execution_route_registry_available": execution_governance_integration_profile.route_registry_available,
                "execution_route_promotion_recommended": execution_governance_integration_profile.route_promotion_recommended,
                "phase10_profile_count": len(phase10_decision_integration_profiles),
                "phase10_allowed_count": sum(1 for profile in phase10_decision_integration_profiles.values() if profile.allowed),
                "phase10_ensemble_profile_count": len(self.ensemble_decision_profiles),
                "phase10_learning_state_available": self.learning_state_registry_profile is not None,
            },
        )

    # ---------------------------------------------------------
    # Symbol pipeline
    # ---------------------------------------------------------

    def _process_symbol(
        self,
        request,
        symbol: str,
    ):
        errors = []
        warnings = []

        price_history = (
            request.price_history_by_symbol.get(
                symbol
            )
        )

        option_chain = (
            request.option_chain_by_symbol.get(
                symbol
            )
        )

        if (
            self.policy.require_price_history
            and self._is_empty(price_history)
        ):
            errors.append(
                "PRICE_HISTORY_UNAVAILABLE"
            )

        if (
            self.policy.require_option_chain
            and self._is_empty(option_chain)
        ):
            errors.append(
                "OPTION_CHAIN_UNAVAILABLE"
            )

        direction = str(
            request.signal_by_symbol.get(
                symbol,
                "NEUTRAL",
            )
            or "NEUTRAL"
        ).upper()

        market_regime = str(
            request.market_regime_by_symbol.get(
                symbol,
                "UNKNOWN",
            )
            or "UNKNOWN"
        ).upper()

        technical_score = self._bound_score(
            request.technical_score_by_symbol.get(
                symbol,
                0.0,
            )
        )

        if (
            technical_score
            < self.policy.minimum_technical_score
        ):
            warnings.append(
                "TECHNICAL_SCORE_BELOW_PREFERRED_MINIMUM"
            )

        underlying_price = (
            self._underlying_price(
                request=request,
                symbol=symbol,
                price_history=price_history,
            )
        )

        if underlying_price <= 0:
            errors.append(
                "UNDERLYING_PRICE_UNAVAILABLE"
            )

        if errors:
            return [], SymbolDecisionDiagnostic(
                symbol=symbol,
                processed=False,
                candidate_count=0,
                accepted_candidate_count=0,
                rejected_candidate_count=0,
                errors=errors,
                warnings=warnings,
            )

        try:
            volatility_profile = (
                self.volatility_engine.analyze(
                    symbol=symbol,
                    price_history=price_history,
                    option_history=option_chain,
                )
            )
        except Exception as exc:
            return [], SymbolDecisionDiagnostic(
                symbol=symbol,
                processed=False,
                candidate_count=0,
                accepted_candidate_count=0,
                rejected_candidate_count=0,
                errors=[
                    "VOLATILITY_ANALYSIS_FAILED: "
                    f"{exc}"
                ],
                warnings=warnings,
            )

        atr = self._safe_float(
            request.atr_by_symbol.get(
                symbol,
                0.0,
            )
        )

        try:
            expected_move_profile = (
                self.expected_move_engine
                .analyze_from_option_chain(
                    symbol=symbol,
                    underlying_price=underlying_price,
                    horizon_days=request.target_dte,
                    option_chain=option_chain,
                    implied_volatility=(
                        self._safe_float(
                            getattr(
                                volatility_profile,
                                "current_iv",
                                0.0,
                            )
                        )
                    ),
                    historical_volatility=(
                        self._safe_float(
                            getattr(
                                volatility_profile,
                                "hv30",
                                0.0,
                            )
                        )
                    ),
                    atr=atr,
                )
            )
        except Exception as exc:
            expected_move_profile = None
            warnings.append(
                "EXPECTED_MOVE_ANALYSIS_FAILED: "
                f"{exc}"
            )

        try:
            strategy_candidates = (
                self.strategy_selector.select(
                    symbol=symbol,
                    direction=direction,
                    market_regime=market_regime,
                    volatility_profile=(
                        volatility_profile
                    ),
                    expected_move_profile=(
                        expected_move_profile
                    ),
                )
            )
        except TypeError:
            strategy_candidates = (
                self.strategy_selector.select(
                    symbol=symbol,
                    direction=direction,
                    market_regime=market_regime,
                    volatility_profile=(
                        volatility_profile
                    ),
                )
            )

        strategy_candidates = strategy_candidates[
            :request.strategy_limit_per_symbol
        ]

        symbol_bundles = []

        for strategy_candidate in strategy_candidates:
            strategy = str(
                getattr(
                    strategy_candidate,
                    "strategy",
                    "",
                )
                or ""
            ).upper()

            expiration_candidates = (
                self.expiration_optimizer.optimize(
                    symbol=symbol,
                    strategy=strategy,
                    underlying_price=(
                        underlying_price
                    ),
                    option_chain=option_chain,
                    volatility_profile=(
                        volatility_profile
                    ),
                    top_n=(
                        request
                        .expiration_limit_per_strategy
                    ),
                )
            )

            if not expiration_candidates:
                bundle = self._rejected_bundle(
                    symbol=symbol,
                    direction=direction,
                    market_regime=market_regime,
                    technical_score=technical_score,
                    underlying_price=underlying_price,
                    strategy_candidate=(
                        strategy_candidate
                    ),
                    volatility_profile=(
                        volatility_profile
                    ),
                    expected_move_profile=(
                        expected_move_profile
                    ),
                    reason=(
                        "NO_EXPIRATION_CANDIDATE"
                    ),
                )

                symbol_bundles.append(bundle)
                continue

            for expiration_candidate in (
                expiration_candidates
            ):
                expiry_chain = self._filter_expiry(
                    option_chain=option_chain,
                    expiry=getattr(
                        expiration_candidate,
                        "expiry",
                        "",
                    ),
                )

                strike_candidates = (
                    self.strike_optimizer.optimize(
                        symbol=symbol,
                        strategy=strategy,
                        underlying_price=(
                            underlying_price
                        ),
                        option_chain=expiry_chain,
                        top_n=(
                            request
                            .strike_limit_per_expiration
                        ),
                    )
                )

                if not strike_candidates:
                    bundle = self._rejected_bundle(
                        symbol=symbol,
                        direction=direction,
                        market_regime=market_regime,
                        technical_score=technical_score,
                        underlying_price=(
                            underlying_price
                        ),
                        strategy_candidate=(
                            strategy_candidate
                        ),
                        expiration_candidate=(
                            expiration_candidate
                        ),
                        volatility_profile=(
                            volatility_profile
                        ),
                        expected_move_profile=(
                            expected_move_profile
                        ),
                        reason=(
                            "NO_STRIKE_CANDIDATE"
                        ),
                    )

                    symbol_bundles.append(bundle)
                    continue

                for strike_candidate in (
                    strike_candidates
                ):
                    bundle = (
                        self._build_candidate_bundle(
                            request=request,
                            symbol=symbol,
                            direction=direction,
                            market_regime=(
                                market_regime
                            ),
                            technical_score=(
                                technical_score
                            ),
                            underlying_price=(
                                underlying_price
                            ),
                            option_chain=(
                                expiry_chain
                            ),
                            strategy_candidate=(
                                strategy_candidate
                            ),
                            expiration_candidate=(
                                expiration_candidate
                            ),
                            strike_candidate=(
                                strike_candidate
                            ),
                            volatility_profile=(
                                volatility_profile
                            ),
                            expected_move_profile=(
                                expected_move_profile
                            ),
                        )
                    )

                    symbol_bundles.append(bundle)

                    if (
                        self.policy
                        .stop_after_first_valid_strike_per_strategy
                        and bundle.allowed
                    ):
                        break

                    if (
                        len(symbol_bundles)
                        >= self.policy
                        .maximum_candidates_per_symbol
                    ):
                        break

                if (
                    len(symbol_bundles)
                    >= self.policy
                    .maximum_candidates_per_symbol
                ):
                    break

            if (
                len(symbol_bundles)
                >= self.policy
                .maximum_candidates_per_symbol
            ):
                break

        accepted = sum(
            1
            for bundle in symbol_bundles
            if bundle.allowed
        )

        diagnostic = SymbolDecisionDiagnostic(
            symbol=symbol,
            processed=True,
            candidate_count=len(
                symbol_bundles
            ),
            accepted_candidate_count=accepted,
            rejected_candidate_count=(
                len(symbol_bundles)
                - accepted
            ),
            errors=errors,
            warnings=warnings,
        )

        return symbol_bundles, diagnostic

    # ---------------------------------------------------------
    # Candidate pipeline
    # ---------------------------------------------------------

    def _build_candidate_bundle(
        self,
        request,
        symbol,
        direction,
        market_regime,
        technical_score,
        underlying_price,
        option_chain,
        strategy_candidate,
        expiration_candidate,
        strike_candidate,
        volatility_profile,
        expected_move_profile,
    ):
        candidate_id = self._candidate_id(
            symbol=symbol,
            strategy=getattr(
                strategy_candidate,
                "strategy",
                "",
            ),
            expiry=getattr(
                expiration_candidate,
                "expiry",
                "",
            ),
            strike_candidate=strike_candidate,
        )

        greeks_profile = (
            self._greeks_profile(
                symbol=symbol,
                strategy_candidate=(
                    strategy_candidate
                ),
                strike_candidate=(
                    strike_candidate
                ),
            )
        )

        liquidity_profile = (
            self._liquidity_profile(
                symbol=symbol,
                strategy_candidate=(
                    strategy_candidate
                ),
                strike_candidate=(
                    strike_candidate
                ),
            )
        )

        payoff_profile = (
            self._payoff_profile(
                symbol=symbol,
                underlying_price=(
                    underlying_price
                ),
                strategy_candidate=(
                    strategy_candidate
                ),
                strike_candidate=(
                    strike_candidate
                ),
                expiration_candidate=(
                    expiration_candidate
                ),
            )
        )

        probability_profile = (
            self._probability_profile(
                strategy_candidate=(
                    strategy_candidate
                ),
                strike_candidate=(
                    strike_candidate
                ),
                payoff_profile=(
                    payoff_profile
                ),
                volatility_profile=(
                    volatility_profile
                ),
                expiration_candidate=(
                    expiration_candidate
                ),
            )
        )

        raw_probability_value = (
            getattr(probability_profile, "probability_of_profit", None)
            if probability_profile is not None
            else None
        )
        probability_calibration_profile = self._probability_calibration_profile(
            raw_probability_value, symbol=symbol,
            strategy=getattr(strategy_candidate, "strategy", ""),
            market_regime=market_regime, direction=direction,
        )

        scenario_profile = (
            self._scenario_profile(
                strike_candidate=(
                    strike_candidate
                ),
                payoff_profile=(
                    payoff_profile
                ),
                volatility_profile=(
                    volatility_profile
                ),
                expiration_candidate=(
                    expiration_candidate
                ),
            )
        )

        distribution_risk_profile = (
            self._distribution_risk_profile(
                symbol=symbol,
                strategy_candidate=(
                    strategy_candidate
                ),
                payoff_profile=(
                    payoff_profile
                ),
                probability_profile=(
                    probability_profile
                ),
                scenario_profile=(
                    scenario_profile
                ),
                strike_candidate=(
                    strike_candidate
                ),
                initial_capital=(
                    getattr(
                        request,
                        "initial_capital",
                        None,
                    )
                ),
            )
        )

        risk_surface_profile = (
            self._risk_surface_profile(
                symbol=symbol,
                strategy_candidate=strategy_candidate,
                underlying_price=underlying_price,
                volatility_profile=volatility_profile,
                expiration_candidate=expiration_candidate,
                greeks_profile=greeks_profile,
                payoff_profile=payoff_profile,
                strike_candidate=strike_candidate,
                initial_capital=getattr(
                    request,
                    "initial_capital",
                    None,
                ),
            )
        )

        context = (
            self.strategy_scoring_engine
            .build_context(
                symbol=symbol,
                strategy_candidate=(
                    strategy_candidate
                ),
                market_regime=market_regime,
                technical_score=(
                    technical_score
                ),
                strike_candidate=(
                    strike_candidate
                ),
                expiration_candidate=(
                    expiration_candidate
                ),
                greeks_profile=(
                    greeks_profile
                ),
                liquidity_profile=(
                    liquidity_profile
                ),
                expected_move_profile=(
                    expected_move_profile
                ),
                volatility_profile=(
                    volatility_profile
                ),
                portfolio_fit_score=(
                    self._bound_score(
                        request
                        .portfolio_fit_by_symbol
                        .get(symbol, 50.0)
                    )
                ),
                risk_reward_score=(
                    self._risk_reward_score(
                        payoff_profile=(
                            payoff_profile
                        ),
                        strike_candidate=(
                            strike_candidate
                        ),
                    )
                ),
            )
        )

        scoring_result = (
            self.strategy_scoring_engine
            .score(context)
        )

        maximum_loss = self._profile_value(
            payoff_profile,
            "maximum_loss",
            default=self._profile_value(
                strike_candidate,
                "max_loss",
                default=0.0,
            ),
        )

        expected_profit = self._profile_value(
            payoff_profile,
            "expected_profit",
            default=self._profile_value(
                strike_candidate,
                "max_profit",
                default=0.0,
            ),
        )

        capital_required = self._profile_value(
            payoff_profile,
            "capital_required",
            default=maximum_loss,
        )

        expected_return_pct = self._profile_value(
            payoff_profile,
            "expected_return_pct",
            default=(
                expected_profit
                / capital_required
                if capital_required > 0
                else 0.0
            ),
        )

        probability_profile_valid = bool(
            probability_profile is not None
            and getattr(
                probability_profile,
                "valid",
                False,
            )
        )

        if probability_profile_valid:
            expected_profit = self._safe_float(
                getattr(
                    probability_profile,
                    "expected_value",
                    expected_profit,
                )
            )
            expected_return_pct = self._safe_float(
                getattr(
                    probability_profile,
                    "expected_return_on_capital",
                    expected_return_pct,
                )
            )

        probability_of_profit = (
            getattr(
                probability_profile,
                "probability_of_profit",
                None,
            )
            if probability_profile_valid
            else self._probability_of_profit(
                strategy_candidate=(
                    strategy_candidate
                ),
                strike_candidate=(
                    strike_candidate
                ),
            )
        )


        try:
            opportunity = (
                self.opportunity_factory.create(
                    symbol=symbol,
                    strategy_scoring_result=(
                        scoring_result
                    ),
                    strategy_candidate=(
                        strategy_candidate
                    ),
                    strike_candidate=(
                        strike_candidate
                    ),
                    expiration_candidate=(
                        expiration_candidate
                    ),
                    greeks_profile=(
                        greeks_profile
                    ),
                    liquidity_profile=(
                        liquidity_profile
                    ),
                    expected_move_profile=(
                        expected_move_profile
                    ),
                    volatility_profile=(
                        volatility_profile
                    ),
                    payoff_profile=(
                        payoff_profile
                    ),
                    probability_profile=(
                        probability_profile
                    ),
                    expected_return_pct=(
                        expected_return_pct
                    ),
                    expected_profit=(
                        expected_profit
                    ),
                    maximum_loss=(
                        maximum_loss
                    ),
                    capital_required=(
                        capital_required
                    ),
                    probability_of_profit=(
                        probability_of_profit
                    ),
                    portfolio_fit_score=(
                        request
                        .portfolio_fit_by_symbol
                        .get(symbol, 50.0)
                    ),
                    sector=(
                        request
                        .sector_by_symbol
                        .get(symbol, "UNKNOWN")
                    ),
                    industry=(
                        request
                        .industry_by_symbol
                        .get(symbol, "UNKNOWN")
                    ),
                    correlation_group=(
                        request
                        .correlation_group_by_symbol
                        .get(symbol, "")
                    ),
                    contracts=1,
                    metadata={
                        "candidate_id":
                            candidate_id,
                    },
                )
            )
        except TypeError:
            opportunity = (
                self.opportunity_factory.create(
                    symbol=symbol,
                    strategy_scoring_result=(
                        scoring_result
                    ),
                    strategy_candidate=(
                        strategy_candidate
                    ),
                    strike_candidate=(
                        strike_candidate
                    ),
                    expiration_candidate=(
                        expiration_candidate
                    ),
                    greeks_profile=(
                        greeks_profile
                    ),
                    liquidity_profile=(
                        liquidity_profile
                    ),
                    expected_move_profile=(
                        expected_move_profile
                    ),
                    volatility_profile=(
                        volatility_profile
                    ),
                    expected_return_pct=(
                        expected_return_pct
                    ),
                    expected_profit=(
                        expected_profit
                    ),
                    maximum_loss=(
                        maximum_loss
                    ),
                    capital_required=(
                        capital_required
                    ),
                    probability_of_profit=(
                        probability_of_profit
                    ),
                    portfolio_fit_score=(
                        request
                        .portfolio_fit_by_symbol
                        .get(symbol, 50.0)
                    ),
                    sector=(
                        request
                        .sector_by_symbol
                        .get(symbol, "UNKNOWN")
                    ),
                    industry=(
                        request
                        .industry_by_symbol
                        .get(symbol, "UNKNOWN")
                    ),
                    correlation_group=(
                        request
                        .correlation_group_by_symbol
                        .get(symbol, "")
                    ),
                    contracts=1,
                    metadata={
                        "candidate_id":
                            candidate_id,
                        "payoff_profile":
                            payoff_profile,
                        "probability_profile":
                            probability_profile,
                        "probability_calibration_profile":
                            probability_calibration_profile,
                    },
                )
            )

        rejection_reasons = (
            self._candidate_rejections(
                technical_score=technical_score,
                strategy_candidate=(
                    strategy_candidate
                ),
                expiration_candidate=(
                    expiration_candidate
                ),
                strike_candidate=(
                    strike_candidate
                ),
                greeks_profile=(
                    greeks_profile
                ),
                liquidity_profile=(
                    liquidity_profile
                ),
                payoff_profile=(
                    payoff_profile
                ),
                scoring_result=(
                    scoring_result
                ),
            )
        )

        if (
            scenario_profile is not None
            and getattr(
                scenario_profile,
                "valid",
                False,
            )
            and not getattr(
                scenario_profile,
                "allowed",
                True,
            )
        ):
            rejection_reasons.extend(
                list(
                    getattr(
                        scenario_profile,
                        "rejection_reasons",
                        [],
                    )
                    or []
                )
            )

        if (
            distribution_risk_profile is not None
            and getattr(
                distribution_risk_profile,
                "valid",
                False,
            )
            and not getattr(
                distribution_risk_profile,
                "allowed",
                True,
            )
        ):
            rejection_reasons.extend(
                list(
                    getattr(
                        distribution_risk_profile,
                        "rejection_reasons",
                        [],
                    )
                    or []
                )
            )

        if (
            risk_surface_profile is not None
            and getattr(risk_surface_profile, "valid", False)
            and not getattr(risk_surface_profile, "allowed", True)
        ):
            rejection_reasons.extend(
                list(
                    getattr(
                        risk_surface_profile,
                        "rejection_reasons",
                        [],
                    )
                    or []
                )
            )

        rejection_reasons = list(
            dict.fromkeys(
                rejection_reasons
            )
        )

        allowed = (
            not rejection_reasons
            and bool(
                getattr(
                    scoring_result,
                    "allowed",
                    False,
                )
            )
        )

        if not allowed:
            opportunity.allowed = False
            opportunity.rank_eligible = False

            opportunity.rejection_reasons = list(
                dict.fromkeys(
                    list(
                        opportunity
                        .rejection_reasons
                    )
                    + rejection_reasons
                )
            )

        warnings = list(
            dict.fromkeys(
                list(
                    getattr(
                        scoring_result,
                        "warnings",
                        [],
                    )
                    or []
                )
                + list(
                    getattr(
                        strike_candidate,
                        "warnings",
                        [],
                    )
                    or []
                )
                + list(
                    getattr(
                        expiration_candidate,
                        "warnings",
                        [],
                    )
                    or []
                )
                + list(
                    getattr(
                        greeks_profile,
                        "warnings",
                        [],
                    )
                    or []
                )
                + list(
                    getattr(
                        liquidity_profile,
                        "warnings",
                        [],
                    )
                    or []
                )
                + list(
                    getattr(
                        probability_profile,
                        "warnings",
                        [],
                    )
                    or []
                )
                + list(
                    getattr(
                        scenario_profile,
                        "warnings",
                        [],
                    )
                    or []
                )
                + list(
                    getattr(
                        distribution_risk_profile,
                        "warnings",
                        [],
                    )
                    or []
                )
                + list(
                    getattr(
                        risk_surface_profile,
                        "warnings",
                        [],
                    )
                    or []
                )
            )
        )

        return DecisionCandidateBundle(
            symbol=symbol,
            direction=direction,
            market_regime=market_regime,
            technical_score=technical_score,
            underlying_price=underlying_price,
            strategy_candidate=(
                strategy_candidate
            ),
            expiration_candidate=(
                expiration_candidate
            ),
            strike_candidate=(
                strike_candidate
            ),
            volatility_profile=(
                volatility_profile
            ),
            expected_move_profile=(
                expected_move_profile
            ),
            greeks_profile=(
                greeks_profile
            ),
            liquidity_profile=(
                liquidity_profile
            ),
            payoff_profile=(
                payoff_profile
            ),
            probability_profile=(
                probability_profile
            ),
            scenario_profile=(
                scenario_profile
            ),
            distribution_risk_profile=(
                distribution_risk_profile
            ),
            risk_surface_profile=(
                risk_surface_profile
            ),
            strategy_scoring_context=(
                context
            ),
            strategy_scoring_result=(
                scoring_result
            ),
            institutional_opportunity=(
                opportunity
            ),
            candidate_id=candidate_id,
            allowed=allowed,
            rejection_reasons=(
                rejection_reasons
            ),
            warnings=warnings,
            metadata={},
        )

    # ---------------------------------------------------------
    # Greeks, liquidity, and payoff helpers
    # ---------------------------------------------------------

    def _greeks_profile(
        self,
        symbol,
        strategy_candidate,
        strike_candidate,
    ):
        attached = getattr(
            strike_candidate,
            "greeks_profile",
            None,
        )

        if attached is not None:
            return attached

        strategy = str(
            getattr(
                strategy_candidate,
                "strategy",
                "",
            )
            or ""
        ).upper()

        if hasattr(
            strike_candidate,
            "delta",
        ):
            return (
                self.greeks_optimizer
                .analyze_single_leg(
                    symbol=symbol,
                    strategy=strategy,
                    delta=getattr(
                        strike_candidate,
                        "delta",
                        0.0,
                    ),
                    gamma=getattr(
                        strike_candidate,
                        "gamma",
                        0.0,
                    ),
                    theta=getattr(
                        strike_candidate,
                        "theta",
                        0.0,
                    ),
                    vega=getattr(
                        strike_candidate,
                        "vega",
                        0.0,
                    ),
                    rho=getattr(
                        strike_candidate,
                        "rho",
                        0.0,
                    ),
                )
            )

        if hasattr(
            strike_candidate,
            "net_delta",
        ):
            return SimpleNamespace(
                symbol=symbol,
                strategy=strategy,
                net_delta=self._safe_float(
                    getattr(
                        strike_candidate,
                        "net_delta",
                        0.0,
                    )
                ),
                net_gamma=self._safe_float(
                    getattr(
                        strike_candidate,
                        "net_gamma",
                        0.0,
                    )
                ),
                net_theta=self._safe_float(
                    getattr(
                        strike_candidate,
                        "net_theta",
                        0.0,
                    )
                ),
                net_vega=self._safe_float(
                    getattr(
                        strike_candidate,
                        "net_vega",
                        0.0,
                    )
                ),
                net_rho=self._safe_float(
                    getattr(
                        strike_candidate,
                        "net_rho",
                        0.0,
                    )
                ),
                composite_score=self._bound_score(
                    getattr(
                        strike_candidate,
                        "greek_score",
                        70.0,
                    )
                ),
                balance_score=self._bound_score(
                    getattr(
                        strike_candidate,
                        "greek_score",
                        70.0,
                    )
                ),
                allowed=bool(
                    getattr(
                        strike_candidate,
                        "allowed",
                        True,
                    )
                ),
                warnings=[],
            )

        return SimpleNamespace(
            symbol=symbol,
            strategy=strategy,
            net_delta=0.0,
            net_gamma=0.0,
            net_theta=0.0,
            net_vega=0.0,
            net_rho=0.0,
            composite_score=0.0,
            balance_score=0.0,
            allowed=False,
            warnings=[
                "Greeks profile unavailable"
            ],
        )

    def _liquidity_profile(
        self,
        symbol,
        strategy_candidate,
        strike_candidate,
    ):
        attached = getattr(
            strike_candidate,
            "liquidity_profile",
            None,
        )

        if attached is not None:
            return attached

        if hasattr(
            strike_candidate,
            "bid",
        ):
            return (
                self.liquidity_engine
                .analyze_contract(
                    symbol=symbol,
                    contract=strike_candidate,
                    requested_contracts=1,
                )
            )

        liquidity_score = self._bound_score(
            getattr(
                strike_candidate,
                "liquidity_score",
                0.0,
            )
        )

        execution_score = self._bound_score(
            getattr(
                strike_candidate,
                "execution_score",
                liquidity_score,
            )
        )

        return SimpleNamespace(
            liquidity_score=liquidity_score,
            package_liquidity_score=(
                liquidity_score
            ),
            execution_score=execution_score,
            allowed=bool(
                getattr(
                    strike_candidate,
                    "allowed",
                    True,
                )
            ),
            warnings=list(
                getattr(
                    strike_candidate,
                    "warnings",
                    [],
                )
                or []
            ),
        )

    def _payoff_profile(
        self,
        symbol,
        underlying_price,
        strategy_candidate,
        strike_candidate,
        expiration_candidate,
    ):
        attached = getattr(
            strike_candidate,
            "payoff_profile",
            None,
        )

        if attached is not None:
            return attached

        structure = getattr(
            strike_candidate,
            "strategy_structure",
            None,
        )

        if structure is not None:
            return (
                self.multi_strategy_service
                .analyze(structure)
            )

        legs = getattr(
            strike_candidate,
            "legs",
            None,
        )

        if legs:
            try:
                _, profile = (
                    self.multi_strategy_service
                    .build_and_analyze(
                        symbol=symbol,
                        strategy=getattr(
                            strategy_candidate,
                            "strategy",
                            "",
                        ),
                        underlying_price=(
                            underlying_price
                        ),
                        legs=legs,
                        contracts=1,
                    )
                )

                return profile
            except Exception:
                return None

        max_profit = self._safe_float(
            getattr(
                strike_candidate,
                "max_profit",
                0.0,
            )
        )

        max_loss = self._safe_float(
            getattr(
                strike_candidate,
                "max_loss",
                0.0,
            )
        )

        if (
            max_profit > 0
            or max_loss > 0
        ):
            expected_profit = (
                min(
                    max_profit * 0.35,
                    max_loss * 0.50,
                )
                if (
                    max_profit > 0
                    and max_loss > 0
                )
                else 0.0
            )

            return SimpleNamespace(
                maximum_profit=max_profit,
                maximum_loss=max_loss,
                capital_required=max_loss,
                expected_profit=expected_profit,
                expected_return_pct=(
                    expected_profit
                    / max_loss
                    if max_loss > 0
                    else 0.0
                ),
                valid=True,
                warnings=[],
            )

        mid = self._safe_float(
            getattr(
                strike_candidate,
                "mid",
                0.0,
            )
        )

        if mid > 0:
            capital = mid * 100.0

            return SimpleNamespace(
                maximum_profit=None,
                maximum_loss=capital,
                capital_required=capital,
                expected_profit=0.0,
                expected_return_pct=0.0,
                valid=True,
                warnings=[],
            )

        return None

    # ---------------------------------------------------------
    # Decision creation
    # ---------------------------------------------------------

    def _build_decision(
        self,
        bundle,
    ):
        opportunity = (
            bundle.institutional_opportunity
        )

        ranked = bundle.ranked_opportunity
        position = bundle.portfolio_position

        scoring = bundle.strategy_scoring_result

        expected_move = bundle.expected_move_profile
        volatility = bundle.volatility_profile
        greeks = bundle.greeks_profile
        liquidity = bundle.liquidity_profile
        payoff = bundle.payoff_profile
        probability = bundle.probability_profile
        probability_calibration = (bundle.metadata or {}).get("probability_calibration_profile")
        scenario = bundle.scenario_profile
        distribution_risk = bundle.distribution_risk_profile
        risk_surface = bundle.risk_surface_profile

        selected = bool(
            position is not None
            or (
                ranked is not None
                and getattr(
                    ranked,
                    "selected",
                    False,
                )
            )
        )

        allowed = bool(
            bundle.allowed
            and (
                ranked is None
                or getattr(
                    ranked,
                    "allowed",
                    False,
                )
            )
        )

        ranking_score = self._safe_float(
            getattr(
                ranked,
                "ranking_score",
                0.0,
            )
        )

        calibration_ranking = (
            self.probability_calibration_ranking_service.evaluate(
                raw_ranking_score=ranking_score,
                calibration_profile=probability_calibration,
            )
        )
        ranking_score = self._safe_float(
            getattr(calibration_ranking, "adjusted_ranking_score", ranking_score)
        )

        strategy_score = self._safe_float(
            getattr(
                scoring,
                "composite_score",
                0.0,
            )
        )

        action = self._decision_action(
            allowed=allowed,
            selected=selected,
            ranking_score=ranking_score,
            scoring_result=scoring,
            ranked_opportunity=ranked,
            portfolio_position=position,
        )

        readiness = self._decision_readiness(
            allowed=allowed,
            selected=selected,
            ranking_score=ranking_score,
            scoring_result=scoring,
            ranked_opportunity=ranked,
            portfolio_position=position,
        )

        rejection_reasons = list(
            dict.fromkeys(
                list(
                    bundle.rejection_reasons
                )
                + list(
                    getattr(
                        scoring,
                        "rejection_reasons",
                        [],
                    )
                    or []
                )
                + list(
                    getattr(
                        ranked,
                        "rejection_reasons",
                        [],
                    )
                    or []
                )
                + list(
                    getattr(calibration_ranking, "rejection_reasons", []) or []
                )
            )
        )

        contracts = (
            int(
                getattr(
                    position,
                    "contracts",
                    0,
                )
                or 0
            )
            if position is not None
            else 0
        )

        capital_required = (
            self._safe_float(
                getattr(
                    position,
                    "capital_required",
                    0.0,
                )
            )
            if position is not None
            else self._profile_value(
                opportunity,
                "capital_required",
                0.0,
            )
        )

        maximum_loss = (
            self._safe_float(
                getattr(
                    position,
                    "maximum_loss",
                    0.0,
                )
            )
            if position is not None
            else self._profile_value(
                opportunity,
                "maximum_loss",
                0.0,
            )
        )

        expected_profit = (
            self._safe_float(
                getattr(
                    position,
                    "expected_profit",
                    0.0,
                )
            )
            if position is not None
            else self._profile_value(
                opportunity,
                "expected_profit",
                0.0,
            )
        )

        expected_return_pct = (
            self._safe_float(
                getattr(
                    position,
                    "expected_return_pct",
                    0.0,
                )
            )
            if position is not None
            else self._profile_value(
                opportunity,
                "expected_return_pct",
                0.0,
            )
        )

        primary_reason = (
            str(
                getattr(
                    ranked,
                    "primary_reason",
                    "",
                )
                or ""
            )
            if ranked is not None
            else str(
                getattr(
                    scoring,
                    "primary_reason",
                    "",
                )
                or ""
            )
        )

        recommendation = (
            str(
                getattr(
                    ranked,
                    "action",
                    "",
                )
                or ""
            )
            if ranked is not None
            else str(
                getattr(
                    scoring,
                    "recommendation",
                    "",
                )
                or ""
            )
        )

        return InstitutionalDecision(
            symbol=bundle.symbol,
            decision_id=(
                bundle.candidate_id
            ),
            action=action,
            readiness=readiness,
            selected=selected,
            allowed=allowed,
            rank=(
                int(
                    getattr(
                        ranked,
                        "rank",
                        0,
                    )
                )
                if ranked is not None
                else None
            ),
            ranking_score=round(
                ranking_score,
                2,
            ),
            strategy_score=round(
                strategy_score,
                2,
            ),
            direction=bundle.direction,
            strategy=bundle.strategy,
            market_regime=(
                bundle.market_regime
            ),
            volatility_regime=str(
                getattr(
                    volatility,
                    "volatility_regime",
                    "UNKNOWN",
                )
                or "UNKNOWN"
            ),
            underlying_price=round(
                bundle.underlying_price,
                4,
            ),
            expiry=bundle.expiry,
            dte=bundle.dte,
            strike=self._optional_float(
                getattr(
                    bundle.strike_candidate,
                    "strike",
                    None,
                )
            ),
            long_strike=self._optional_float(
                getattr(
                    bundle.strike_candidate,
                    "long_strike",
                    None,
                )
            ),
            short_strike=self._optional_float(
                getattr(
                    bundle.strike_candidate,
                    "short_strike",
                    None,
                )
            ),
            option_symbol=str(
                getattr(
                    bundle.strike_candidate,
                    "option_symbol",
                    "",
                )
                or ""
            ),
            contracts=contracts,
            capital_required=round(
                capital_required,
                2,
            ),
            maximum_loss=round(
                maximum_loss,
                2,
            ),
            expected_profit=round(
                expected_profit,
                2,
            ),
            expected_return_pct=round(
                expected_return_pct,
                4,
            ),
            probability_of_profit=(
                getattr(probability_calibration, "calibrated_probability", None)
                if probability_calibration is not None and getattr(probability_calibration, "valid", False)
                else (getattr(probability, "probability_of_profit", None)
                    if probability is not None and getattr(probability, "valid", False)
                    else getattr(opportunity, "probability_of_profit", None))
            ),
            expected_value=round(
                self._profile_value(
                    probability,
                    "expected_value",
                    0.0,
                ),
                2,
            ),
            expected_return_on_risk=round(
                self._profile_value(
                    probability,
                    "expected_return_on_risk",
                    0.0,
                ),
                4,
            ),
            probability_of_max_profit=(
                getattr(probability, "probability_of_max_profit", None)
                if probability is not None
                else None
            ),
            probability_of_max_loss=(
                getattr(probability, "probability_of_max_loss", None)
                if probability is not None
                else None
            ),
            probability_profit_target=(
                getattr(probability, "probability_profit_target", None)
                if probability is not None
                else None
            ),
            probability_stop_loss=(
                getattr(probability, "probability_stop_loss", None)
                if probability is not None
                else None
            ),
            value_at_risk_95=round(
                self._profile_value(
                    probability,
                    "value_at_risk_95",
                    0.0,
                ),
                2,
            ),
            conditional_value_at_risk_95=round(
                self._profile_value(
                    probability,
                    "conditional_value_at_risk_95",
                    0.0,
                ),
                2,
            ),
            probability_method=str(
                getattr(probability, "method", "UNAVAILABLE")
                or "UNAVAILABLE"
            ),
            probability_simulation_count=int(
                self._profile_value(
                    probability,
                    "simulation_count",
                    0,
                )
            ),
            probability_confidence_score=round(
                self._profile_value(
                    probability,
                    "confidence_score",
                    0.0,
                ),
                2,
            ),
            probability_confidence_grade=str(
                getattr(probability, "confidence_grade", "N/A")
                or "N/A"
            ),
            stress_score=round(
                self._profile_value(
                    scenario,
                    "stress_score",
                    0.0,
                ),
                2,
            ),
            stress_grade=str(
                getattr(
                    scenario,
                    "stress_grade",
                    "N/A",
                )
                or "N/A"
            ),
            stress_risk_severity=str(
                getattr(
                    scenario,
                    "risk_severity",
                    "UNKNOWN",
                )
                or "UNKNOWN"
            ),
            worst_scenario_name=str(
                getattr(
                    scenario,
                    "worst_scenario_name",
                    "",
                )
                or ""
            ),
            worst_scenario_pnl=round(
                self._profile_value(
                    scenario,
                    "worst_scenario_pnl",
                    0.0,
                ),
                2,
            ),
            maximum_stress_loss=round(
                self._profile_value(
                    scenario,
                    "maximum_stress_loss",
                    0.0,
                ),
                2,
            ),
            maximum_stress_loss_pct_of_capital=round(
                self._profile_value(
                    scenario,
                    "maximum_stress_loss_pct_of_capital",
                    0.0,
                ),
                4,
            ),
            maximum_stress_loss_pct_of_maximum_loss=(
                getattr(
                    scenario,
                    "maximum_stress_loss_pct_of_maximum_loss",
                    None,
                )
                if scenario is not None
                else None
            ),
            scenario_allowed=bool(
                getattr(
                    scenario,
                    "allowed",
                    False,
                )
                if scenario is not None
                else False
            ),
            distribution_observation_count=int(
                self._profile_value(
                    distribution_risk,
                    "observation_count",
                    0,
                )
            ),
            historical_var_95=round(
                self._profile_value(
                    distribution_risk,
                    "historical_var",
                    0.0,
                ),
                2,
            ),
            historical_expected_shortfall_95=round(
                self._profile_value(
                    distribution_risk,
                    "historical_expected_shortfall",
                    0.0,
                ),
                2,
            ),
            parametric_var_95=round(
                self._profile_value(
                    distribution_risk,
                    "parametric_var",
                    0.0,
                ),
                2,
            ),
            parametric_expected_shortfall_95=round(
                self._profile_value(
                    distribution_risk,
                    "parametric_expected_shortfall",
                    0.0,
                ),
                2,
            ),
            historical_var_99=round(
                self._profile_value(
                    distribution_risk,
                    "historical_var_99",
                    0.0,
                ),
                2,
            ),
            historical_expected_shortfall_99=round(
                self._profile_value(
                    distribution_risk,
                    "historical_expected_shortfall_99",
                    0.0,
                ),
                2,
            ),
            downside_deviation=round(
                self._profile_value(
                    distribution_risk,
                    "downside_deviation",
                    0.0,
                ),
                6,
            ),
            skewness=round(
                self._profile_value(
                    distribution_risk,
                    "skewness",
                    0.0,
                ),
                4,
            ),
            excess_kurtosis=round(
                self._profile_value(
                    distribution_risk,
                    "excess_kurtosis",
                    0.0,
                ),
                4,
            ),
            probability_of_large_loss=round(
                self._profile_value(
                    distribution_risk,
                    "probability_of_large_loss",
                    0.0,
                ),
                4,
            ),
            probability_of_severe_loss=round(
                self._profile_value(
                    distribution_risk,
                    "probability_of_severe_loss",
                    0.0,
                ),
                4,
            ),
            probability_of_critical_loss=round(
                self._profile_value(
                    distribution_risk,
                    "probability_of_critical_loss",
                    0.0,
                ),
                4,
            ),
            drawdown_at_risk=round(
                self._profile_value(
                    distribution_risk,
                    "drawdown_at_risk",
                    0.0,
                ),
                4,
            ),
            expected_drawdown_shortfall=round(
                self._profile_value(
                    distribution_risk,
                    "expected_drawdown_shortfall",
                    0.0,
                ),
                4,
            ),
            ulcer_index=round(
                self._profile_value(
                    distribution_risk,
                    "ulcer_index",
                    0.0,
                ),
                4,
            ),
            pain_index=round(
                self._profile_value(
                    distribution_risk,
                    "pain_index",
                    0.0,
                ),
                4,
            ),
            omega_ratio=(
                getattr(distribution_risk, "omega_ratio", None)
                if distribution_risk is not None
                else None
            ),
            sortino_ratio=(
                getattr(distribution_risk, "sortino_ratio", None)
                if distribution_risk is not None
                else None
            ),
            gain_to_pain_ratio=(
                getattr(distribution_risk, "gain_to_pain_ratio", None)
                if distribution_risk is not None
                else None
            ),
            tail_risk_score=round(
                self._profile_value(
                    distribution_risk,
                    "tail_risk_score",
                    0.0,
                ),
                2,
            ),
            tail_risk_grade=str(
                getattr(distribution_risk, "tail_risk_grade", "N/A")
                or "N/A"
            ),
            tail_risk_severity=str(
                getattr(distribution_risk, "risk_severity", "UNKNOWN")
                or "UNKNOWN"
            ),
            distribution_risk_allowed=bool(
                getattr(distribution_risk, "allowed", False)
                if distribution_risk is not None
                else False
            ),
            risk_surface_point_count=int(
                self._profile_value(risk_surface, "point_count", 0)
            ),
            risk_surface_worst_case_pnl=round(
                self._profile_value(risk_surface, "worst_case_pnl", 0.0), 2
            ),
            risk_surface_best_case_pnl=round(
                self._profile_value(risk_surface, "best_case_pnl", 0.0), 2
            ),
            risk_surface_base_case_pnl=round(
                self._profile_value(risk_surface, "base_case_pnl", 0.0), 2
            ),
            risk_surface_maximum_loss_pct_of_capital=round(
                self._profile_value(
                    risk_surface, "maximum_loss_pct_of_capital", 0.0
                ),
                4,
            ),
            risk_surface_maximum_gain_pct_of_capital=round(
                self._profile_value(
                    risk_surface, "maximum_gain_pct_of_capital", 0.0
                ),
                4,
            ),
            risk_surface_worst_price_shock_pct=round(
                self._profile_value(risk_surface, "worst_price_shock_pct", 0.0),
                4,
            ),
            risk_surface_worst_volatility_shock=round(
                self._profile_value(
                    risk_surface, "worst_volatility_shock", 0.0
                ),
                4,
            ),
            risk_surface_worst_time_offset_days=int(
                self._profile_value(
                    risk_surface, "worst_time_offset_days", 0
                )
            ),
            delta_gamma_error_estimate=round(
                self._profile_value(
                    risk_surface, "delta_gamma_error_estimate", 0.0
                ),
                4,
            ),
            nonlinear_exposure_score=round(
                self._profile_value(
                    risk_surface, "nonlinear_exposure_score", 0.0
                ),
                2,
            ),
            gamma_risk_score=round(
                self._profile_value(risk_surface, "gamma_risk_score", 0.0), 2
            ),
            vega_risk_score=round(
                self._profile_value(risk_surface, "vega_risk_score", 0.0), 2
            ),
            theta_risk_score=round(
                self._profile_value(risk_surface, "theta_risk_score", 0.0), 2
            ),
            risk_surface_score=round(
                self._profile_value(risk_surface, "surface_score", 0.0), 2
            ),
            risk_surface_grade=str(
                getattr(risk_surface, "surface_grade", "N/A") or "N/A"
            ),
            risk_surface_severity=str(
                getattr(risk_surface, "risk_severity", "UNKNOWN") or "UNKNOWN"
            ),
            risk_surface_allowed=bool(
                getattr(risk_surface, "allowed", False)
                if risk_surface is not None
                else False
            ),
            expected_move=round(
                self._profile_value(
                    expected_move,
                    "blended_move",
                    0.0,
                ),
                4,
            ),
            expected_move_pct=round(
                self._profile_value(
                    expected_move,
                    "blended_move_pct",
                    0.0,
                ),
                2,
            ),
            expected_range_low=round(
                self._profile_value(
                    expected_move,
                    "lower_bound",
                    0.0,
                ),
                4,
            ),
            expected_range_high=round(
                self._profile_value(
                    expected_move,
                    "upper_bound",
                    0.0,
                ),
                4,
            ),
            net_delta=round(
                self._profile_value(
                    position,
                    "delta",
                    self._profile_value(
                        greeks,
                        "net_delta",
                        0.0,
                    ),
                ),
                4,
            ),
            net_gamma=round(
                self._profile_value(
                    position,
                    "gamma",
                    self._profile_value(
                        greeks,
                        "net_gamma",
                        0.0,
                    ),
                ),
                5,
            ),
            net_theta=round(
                self._profile_value(
                    position,
                    "theta",
                    self._profile_value(
                        greeks,
                        "net_theta",
                        0.0,
                    ),
                ),
                4,
            ),
            net_vega=round(
                self._profile_value(
                    position,
                    "vega",
                    self._profile_value(
                        greeks,
                        "net_vega",
                        0.0,
                    ),
                ),
                4,
            ),
            net_rho=round(
                self._profile_value(
                    position,
                    "rho",
                    self._profile_value(
                        greeks,
                        "net_rho",
                        0.0,
                    ),
                ),
                4,
            ),
            liquidity_score=round(
                self._profile_value(
                    liquidity,
                    "package_liquidity_score",
                    self._profile_value(
                        liquidity,
                        "liquidity_score",
                        0.0,
                    ),
                ),
                2,
            ),
            execution_score=round(
                self._profile_value(
                    liquidity,
                    "execution_score",
                    0.0,
                ),
                2,
            ),
            greeks_score=round(
                self._profile_value(
                    greeks,
                    "composite_score",
                    self._profile_value(
                        greeks,
                        "balance_score",
                        0.0,
                    ),
                ),
                2,
            ),
            data_confidence_score=round(
                self._profile_value(
                    getattr(
                        scoring,
                        "breakdown",
                        None,
                    ),
                    "data_confidence_score",
                    0.0,
                ),
                2,
            ),
            portfolio_fit_score=round(
                self._profile_value(
                    opportunity,
                    "portfolio_fit_score",
                    0.0,
                ),
                2,
            ),
            premium_type=str(
                getattr(
                    opportunity,
                    "premium_type",
                    "",
                )
                or ""
            ),
            risk_profile=str(
                getattr(
                    opportunity,
                    "risk_profile",
                    "DEFINED_RISK",
                )
                or "DEFINED_RISK"
            ),
            complexity=str(
                getattr(
                    opportunity,
                    "complexity",
                    "STANDARD",
                )
                or "STANDARD"
            ),
            sector=str(
                getattr(
                    opportunity,
                    "sector",
                    "UNKNOWN",
                )
                or "UNKNOWN"
            ),
            industry=str(
                getattr(
                    opportunity,
                    "industry",
                    "UNKNOWN",
                )
                or "UNKNOWN"
            ),
            correlation_group=str(
                getattr(
                    opportunity,
                    "correlation_group",
                    "",
                )
                or ""
            ),
            primary_reason=primary_reason,
            recommendation=(
                recommendation
            ),
            rejection_reasons=(
                rejection_reasons
            ),
            warnings=list(
                dict.fromkeys(
                    bundle.warnings
                    + list(
                        getattr(
                            ranked,
                            "warnings",
                            [],
                        )
                        or []
                    )
                )
            ),
            strengths=list(
                getattr(
                    ranked,
                    "strengths",
                    getattr(
                        scoring,
                        "strengths",
                        [],
                    ),
                )
                or []
            ),
            weaknesses=list(
                getattr(
                    ranked,
                    "weaknesses",
                    getattr(
                        scoring,
                        "weaknesses",
                        [],
                    ),
                )
                or []
            ),
            score_breakdown=getattr(
                scoring,
                "breakdown",
                None,
            ),
            ranking_breakdown=getattr(
                ranked,
                "breakdown",
                None,
            ),
            payoff_profile=payoff,
            probability_profile=probability,
            scenario_profile=scenario,
            distribution_risk_profile=distribution_risk,
            risk_surface_profile=risk_surface,
            portfolio_position=position,
            metadata={
                "candidate_metadata":
                    dict(bundle.metadata),
                "probability_calibration_profile": probability_calibration,
                "probability_calibration_ranking_profile": calibration_ranking,
            },
        )

    # ---------------------------------------------------------
    # Rejection policy
    # ---------------------------------------------------------

    def _candidate_rejections(
        self,
        technical_score,
        strategy_candidate,
        expiration_candidate,
        strike_candidate,
        greeks_profile,
        liquidity_profile,
        payoff_profile,
        scoring_result,
    ):
        reasons = []

        if (
            technical_score
            < self.policy.minimum_technical_score
        ):
            reasons.append(
                "TECHNICAL_SCORE_BELOW_MINIMUM"
            )

        if (
            self.policy.require_allowed_strategy
            and not bool(
                getattr(
                    strategy_candidate,
                    "allowed",
                    True,
                )
            )
        ):
            reasons.append(
                "STRATEGY_NOT_ALLOWED"
            )

        if (
            self.policy.require_allowed_expiration
            and not bool(
                getattr(
                    expiration_candidate,
                    "allowed",
                    True,
                )
            )
        ):
            reasons.append(
                "EXPIRATION_NOT_ALLOWED"
            )

        if (
            self.policy.require_allowed_strike
            and not bool(
                getattr(
                    strike_candidate,
                    "allowed",
                    True,
                )
            )
        ):
            reasons.append(
                "STRIKE_NOT_ALLOWED"
            )

        if (
            self.policy.require_allowed_greeks
            and not bool(
                getattr(
                    greeks_profile,
                    "allowed",
                    True,
                )
            )
        ):
            reasons.append(
                "GREEKS_NOT_ALLOWED"
            )

        if (
            self.policy.require_allowed_liquidity
            and not bool(
                getattr(
                    liquidity_profile,
                    "allowed",
                    True,
                )
            )
        ):
            reasons.append(
                "LIQUIDITY_NOT_ALLOWED"
            )

        greeks_score = self._profile_value(
            greeks_profile,
            "composite_score",
            self._profile_value(
                greeks_profile,
                "balance_score",
                0.0,
            ),
        )

        if (
            greeks_score
            < self.policy.minimum_greeks_score
        ):
            reasons.append(
                "GREEKS_SCORE_BELOW_MINIMUM"
            )

        liquidity_score = self._profile_value(
            liquidity_profile,
            "package_liquidity_score",
            self._profile_value(
                liquidity_profile,
                "liquidity_score",
                0.0,
            ),
        )

        if (
            liquidity_score
            < self.policy.minimum_liquidity_score
        ):
            reasons.append(
                "LIQUIDITY_SCORE_BELOW_MINIMUM"
            )

        execution_score = self._profile_value(
            liquidity_profile,
            "execution_score",
            0.0,
        )

        if (
            execution_score
            < self.policy.minimum_execution_score
        ):
            reasons.append(
                "EXECUTION_SCORE_BELOW_MINIMUM"
            )

        strategy_score = self._profile_value(
            scoring_result,
            "composite_score",
            0.0,
        )

        if (
            strategy_score
            < self.policy.minimum_strategy_score
        ):
            reasons.append(
                "STRATEGY_SCORE_BELOW_MINIMUM"
            )

        risk_profile = str(
            getattr(
                strategy_candidate,
                "risk_profile",
                "DEFINED_RISK",
            )
            or "DEFINED_RISK"
        ).upper()

        if (
            self.policy.reject_undefined_risk
            and risk_profile
            == "UNDEFINED_RISK"
        ):
            reasons.append(
                "UNDEFINED_RISK_NOT_ALLOWED"
            )

        if payoff_profile is None:
            if (
                not self.policy
                .allow_missing_payoff_profile
            ):
                reasons.append(
                    "PAYOFF_PROFILE_UNAVAILABLE"
                )
        else:
            maximum_loss = self._profile_value(
                payoff_profile,
                "maximum_loss",
                0.0,
            )

            if (
                self.policy
                .reject_missing_maximum_loss
                and maximum_loss <= 0
            ):
                reasons.append(
                    "MAXIMUM_LOSS_UNAVAILABLE"
                )

        return list(
            dict.fromkeys(reasons)
        )


    def _portfolio_optimization_profile(self, decisions, initial_capital):
        candidates = [
            decision for decision in decisions
            if bool(getattr(decision, "allowed", False))
        ]
        if not candidates:
            return None
        try:
            return self.portfolio_optimization_service.optimize(
                candidates=candidates,
                initial_capital=float(initial_capital or 0.0),
            )
        except Exception as exc:
            return SimpleNamespace(
                valid=False, allowed=False, allocations=[],
                rejection_reasons=["PORTFOLIO_OPTIMIZATION_FAILED"],
                warnings=[f"Portfolio optimization failed: {exc}"],
                metadata={"exception_type": type(exc).__name__},
            )

    def _attach_optimization_recommendations(
        self, decisions, profile, apply_selection=False
    ):
        allocation_by_id = {}
        if profile is not None:
            allocation_by_id = {
                str(item.candidate_id): item
                for item in getattr(profile, "allocations", []) or []
            }
        for decision in decisions:
            allocation = allocation_by_id.get(str(decision.decision_id))
            selected = allocation is not None
            decision.optimization_selected = selected
            decision.optimization_status = (
                "SELECTED" if selected else
                "REJECTED" if profile is not None else "UNAVAILABLE"
            )
            if selected:
                decision.optimized_allocation_dollars = float(
                    allocation.allocation_dollars or 0.0
                )
                decision.optimized_allocation_weight_pct = float(
                    allocation.allocation_weight_pct or 0.0
                )
                decision.optimized_allocation_multiplier = float(
                    allocation.allocation_multiplier or 0.0
                )
                decision.optimized_expected_profit = float(
                    allocation.expected_profit or 0.0
                )
                decision.optimized_maximum_loss = float(
                    allocation.maximum_loss or 0.0
                )
                decision.optimization_marginal_score = float(
                    allocation.marginal_objective_score or 0.0
                )
            decision.metadata["portfolio_optimization_profile"] = profile
            decision.metadata["optimization_selected"] = selected
            if apply_selection:
                decision.selected = selected


    def _portfolio_optimization_frontier_profile(self, decisions, initial_capital):
        candidates = [decision for decision in decisions if bool(getattr(decision, "allowed", False))]
        if not candidates:
            return None
        try:
            return self.portfolio_optimization_frontier_service.analyze(
                candidates=candidates, initial_capital=float(initial_capital or 0.0)
            )
        except Exception as exc:
            return SimpleNamespace(valid=False, allowed=False, points=[], pareto_points=[], rejection_reasons=["PORTFOLIO_OPTIMIZATION_FRONTIER_FAILED"], warnings=[f"Portfolio optimization frontier failed: {exc}"], metadata={"exception_type": type(exc).__name__})

    def _portfolio_optimization_recommendation(self, frontier_profile):
        try:
            return self.portfolio_optimization_recommendation_service.recommend(
                frontier_profile=frontier_profile,
                base_policy=self.portfolio_optimization_service.policy,
            )
        except Exception as exc:
            return SimpleNamespace(valid=False, allowed=False, source_point_id=None, confidence_score=0.0, recommendation_grade="F", rejection_reasons=["PORTFOLIO_OPTIMIZATION_RECOMMENDATION_FAILED"], warnings=[f"Portfolio optimization recommendation failed: {exc}"], metadata={"exception_type": type(exc).__name__})

    def _attach_frontier_recommendation(self, decisions, frontier_profile, recommendation, applied):
        valid = bool(recommendation is not None and getattr(recommendation, "valid", False))
        for decision in decisions:
            decision.frontier_recommended = valid and bool(getattr(recommendation, "allowed", False))
            decision.frontier_point_id = getattr(recommendation, "source_point_id", None)
            decision.frontier_confidence_score = float(getattr(recommendation, "confidence_score", 0.0) or 0.0)
            decision.frontier_recommendation_grade = str(getattr(recommendation, "recommendation_grade", "N/A") or "N/A")
            decision.frontier_policy_applied = bool(applied and decision.frontier_recommended)
            decision.metadata["portfolio_optimization_frontier_profile"] = frontier_profile
            decision.metadata["portfolio_optimization_recommendation"] = recommendation
            decision.metadata["frontier_policy_applied"] = decision.frontier_policy_applied

    def _portfolio_risk_surface_profile(self, selected_decisions, initial_capital):
        profiles=[]; allocations=[]; metadata=[]
        for decision in selected_decisions:
            profile=getattr(decision, "risk_surface_profile", None)
            if profile is None or not getattr(profile, "valid", False):
                continue
            profiles.append(profile)
            position=getattr(decision, "portfolio_position", None)
            allocated=float(getattr(position, "capital_required", 0.0) or getattr(decision, "capital_required", 0.0) or 0.0)
            profile_capital=float(getattr(profile, "capital_required", 0.0) or allocated or 1.0)
            allocations.append(allocated / profile_capital if profile_capital > 0 else 1.0)
            metadata.append({
                "position_id": getattr(position, "position_id", decision.decision_id),
                "strategy": decision.strategy,
                "sector": decision.sector,
                "correlation_group": decision.correlation_group,
            })
        if not profiles:
            return None
        try:
            return self.risk_surface_service.analyze_portfolio(
                profiles=profiles, initial_capital=float(initial_capital or 0.0),
                allocations=allocations, position_metadata=metadata,
            )
        except Exception:
            return None

    # ---------------------------------------------------------
    # General helpers
    # ---------------------------------------------------------

    def _rejected_bundle(
        self,
        symbol,
        direction,
        market_regime,
        technical_score,
        underlying_price,
        reason,
        strategy_candidate=None,
        expiration_candidate=None,
        volatility_profile=None,
        expected_move_profile=None,
    ):
        return DecisionCandidateBundle(
            symbol=symbol,
            direction=direction,
            market_regime=market_regime,
            technical_score=technical_score,
            underlying_price=underlying_price,
            strategy_candidate=(
                strategy_candidate
            ),
            expiration_candidate=(
                expiration_candidate
            ),
            volatility_profile=(
                volatility_profile
            ),
            expected_move_profile=(
                expected_move_profile
            ),
            candidate_id=(
                self._candidate_id(
                    symbol=symbol,
                    strategy=getattr(
                        strategy_candidate,
                        "strategy",
                        "NONE",
                    ),
                    expiry=getattr(
                        expiration_candidate,
                        "expiry",
                        "",
                    ),
                    strike_candidate=None,
                )
            ),
            allowed=False,
            rejection_reasons=[
                reason
            ],
        )

    def _attach_portfolio_positions(
        self,
        bundles,
        portfolio_result,
    ):
        if portfolio_result is None:
            return

        for position in (
            portfolio_result.positions
        ):
            source_ranked = getattr(
                position,
                "source_ranked_opportunity",
                None,
            )

            if source_ranked is None:
                continue

            for bundle in bundles:
                if (
                    bundle.ranked_opportunity
                    is source_ranked
                ):
                    bundle.portfolio_position = (
                        position
                    )
                    break

    def _underlying_price(
        self,
        request,
        symbol,
        price_history,
    ):
        explicit = self._safe_float(
            request
            .underlying_price_by_symbol
            .get(symbol, 0.0)
        )

        if explicit > 0:
            return explicit

        if price_history is None:
            return 0.0

        if hasattr(
            price_history,
            "columns",
        ):
            for column in [
                "close",
                "Close",
                "price",
            ]:
                if column in price_history.columns:
                    values = (
                        price_history[column]
                        .dropna()
                    )

                    if not values.empty:
                        return self._safe_float(
                            values.iloc[-1]
                        )

        if isinstance(
            price_history,
            list,
        ):
            for row in reversed(
                price_history
            ):
                value = (
                    row.get("close")
                    or row.get("Close")
                    or row.get("price")
                )

                parsed = self._safe_float(
                    value
                )

                if parsed > 0:
                    return parsed

        return 0.0

    def _filter_expiry(
        self,
        option_chain,
        expiry,
    ):
        if not expiry:
            return option_chain

        if hasattr(
            option_chain,
            "columns",
        ):
            for column in [
                "expiry",
                "expiration",
                "expiration_date",
            ]:
                if column in option_chain.columns:
                    mask = (
                        option_chain[column]
                        .astype(str)
                        == str(expiry)
                    )

                    return (
                        option_chain.loc[mask]
                        .copy()
                    )

            return option_chain

        if isinstance(
            option_chain,
            list,
        ):
            return [
                row
                for row in option_chain
                if str(
                    row.get("expiry")
                    or row.get("expiration")
                    or row.get(
                        "expiration_date"
                    )
                    or ""
                )
                == str(expiry)
            ]

        return option_chain

    def _candidate_id(
        self,
        symbol,
        strategy,
        expiry,
        strike_candidate,
    ):
        strike_text = ""

        if strike_candidate is not None:
            if hasattr(
                strike_candidate,
                "strike",
            ):
                strike_text = str(
                    getattr(
                        strike_candidate,
                        "strike",
                        "",
                    )
                )
            else:
                strike_text = (
                    f"{getattr(strike_candidate, 'long_strike', '')}"
                    "-"
                    f"{getattr(strike_candidate, 'short_strike', '')}"
                )

        suffix = uuid4().hex[:8]

        return (
            f"{str(symbol).upper()}_"
            f"{str(strategy).upper()}_"
            f"{expiry}_"
            f"{strike_text}_"
            f"{suffix}"
        )

    def _probability_of_profit(
        self,
        strategy_candidate,
        strike_candidate,
    ):
        for obj in [
            strike_candidate,
            strategy_candidate,
        ]:
            if obj is None:
                continue

            for field in [
                "probability_of_profit",
                "pop",
            ]:
                value = getattr(
                    obj,
                    field,
                    None,
                )

                if value is not None:
                    probability = (
                        self._safe_float(
                            value
                        )
                    )

                    if probability > 1:
                        probability /= 100.0

                    return max(
                        0.0,
                        min(
                            1.0,
                            probability,
                        ),
                    )

        return None

    def _risk_reward_score(
        self,
        payoff_profile,
        strike_candidate,
    ):
        if payoff_profile is not None:
            ratio = getattr(
                payoff_profile,
                "risk_reward_ratio",
                None,
            )

            if ratio is not None:
                ratio = self._safe_float(
                    ratio
                )

                if ratio >= 2:
                    return 100.0

                if ratio >= 1:
                    return 90.0

                if ratio >= 0.50:
                    return 75.0

                if ratio >= 0.33:
                    return 65.0

                if ratio >= 0.20:
                    return 50.0

                return 30.0

        return self._bound_score(
            getattr(
                strike_candidate,
                "risk_reward_score",
                getattr(
                    strike_candidate,
                    "risk_score",
                    50.0,
                ),
            )
        )

    def _decision_action(
        self,
        allowed,
        selected,
        ranking_score,
        scoring_result,
        ranked_opportunity,
        portfolio_position,
    ):
        if not allowed:
            return "REJECT"

        if portfolio_position is not None:
            if (
                ranking_score
                >= self.policy
                .priority_candidate_score
            ):
                return "PRIORITY_EXECUTION_CANDIDATE"

            if (
                ranking_score
                >= self.policy
                .live_candidate_score
            ):
                return "EXECUTION_CANDIDATE"

            return "PAPER_TRADE_POSITION"

        if selected:
            return "SHORTLISTED"

        if (
            ranking_score
            >= self.policy.live_candidate_score
        ):
            return "LIVE_WATCHLIST"

        if (
            ranking_score
            >= self.policy.paper_trade_score
        ):
            return "PAPER_TRADE_WATCHLIST"

        return "RESEARCH_ONLY"

    def _decision_readiness(
        self,
        allowed,
        selected,
        ranking_score,
        scoring_result,
        ranked_opportunity,
        portfolio_position,
    ):
        if not allowed:
            return "REJECTED"

        if portfolio_position is not None:
            if (
                ranking_score
                >= self.policy
                .live_candidate_score
            ):
                return "PORTFOLIO_READY"

            return "PAPER_PORTFOLIO_READY"

        if selected:
            return "SHORTLIST_READY"

        return str(
            getattr(
                ranked_opportunity,
                "tier",
                getattr(
                    scoring_result,
                    "readiness",
                    "RESEARCH_ONLY",
                ),
            )
            or "RESEARCH_ONLY"
        )

    def _overall_readiness(
        self,
        decisions,
        portfolio_result,
    ):
        if (
            portfolio_result is not None
            and getattr(
                portfolio_result,
                "valid",
                False,
            )
        ):
            return str(
                getattr(
                    portfolio_result,
                    "readiness",
                    "PORTFOLIO_READY",
                )
            )

        if any(
            decision.allowed
            and decision.ranking_score
            >= self.policy.live_candidate_score
            for decision in decisions
        ):
            return "LIVE_CANDIDATES_AVAILABLE"

        if any(
            decision.allowed
            for decision in decisions
        ):
            return "RESEARCH_CANDIDATES_AVAILABLE"

        return "NO_VALID_CANDIDATES"

    def _overall_action(
        self,
        decisions,
        portfolio_result,
    ):
        if (
            portfolio_result is not None
            and getattr(
                portfolio_result,
                "positions",
                [],
            )
        ):
            return "REVIEW_PORTFOLIO_RECOMMENDATIONS"

        if any(
            decision.action
            in {
                "LIVE_WATCHLIST",
                "SHORTLISTED",
            }
            for decision in decisions
        ):
            return "REVIEW_SHORTLIST"

        return "NO_ACTION"

    def _is_empty(self, value):
        if value is None:
            return True

        if hasattr(
            value,
            "empty",
        ):
            return bool(value.empty)

        try:
            return len(value) == 0
        except TypeError:
            return False

    def _profile_value(
        self,
        obj,
        field,
        default=0.0,
    ):
        if obj is None:
            return self._safe_float(
                default
            )

        if isinstance(
            obj,
            dict,
        ):
            value = obj.get(
                field,
                default,
            )
        else:
            value = getattr(
                obj,
                field,
                default,
            )

        if value is None:
            return self._safe_float(
                default
            )

        return self._safe_float(
            value,
            default=default,
        )

    def _optional_float(self, value):
        if value is None:
            return None

        return self._safe_float(
            value
        )

    def _bound_score(self, value):
        return max(
            0.0,
            min(
                100.0,
                self._safe_float(value),
            ),
        )

    def _safe_float(
        self,
        value,
        default=0.0,
    ):
        try:
            result = float(value)

            if (
                math.isnan(result)
                or math.isinf(result)
            ):
                return float(default)

            return result

        except (
            TypeError,
            ValueError,
        ):
            return float(default)
