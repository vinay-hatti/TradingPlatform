import math
from types import SimpleNamespace
from uuid import uuid4
from trading_ai.strategy_engine.probability_service import (
    ProbabilityService,
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
        structure = getattr(
            strike_candidate,
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
        )

        if volatility <= 0:
            volatility = self._safe_float(
                getattr(
                    strike_candidate,
                    "implied_volatility",
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
                    getattr(
                        payoff_profile,
                        "maximum_profit",
                        None,
                    )
                    if payoff_profile is not None
                    else None
                ),
                maximum_loss=(
                    getattr(
                        payoff_profile,
                        "maximum_loss",
                        None,
                    )
                    if payoff_profile is not None
                    else None
                ),
                capital_required=(
                    getattr(
                        payoff_profile,
                        "capital_required",
                        None,
                    )
                    if payoff_profile is not None
                    else None
                ),
            )
        except Exception:
            return None


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
        portfolio_service=None,
        portfolio_limits: PortfolioRiskLimits | None = None,
        probability_service=None,
        probability_profile=(
            probability_profile
        ),
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

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def run(
        self,
        request,
    ) -> DecisionRunResult:
        bundles = []
        diagnostics = []

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

        selected_decisions = [
            decision
            for decision in decisions
            if decision.selected
        ]

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


        probability_of_profit = (
            getattr(
                probability_profile,
                "probability_of_profit",
                None,
            )
            if probability_profile is not None
            and getattr(
                probability_profile,
                "valid",
                False,
            )
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
                getattr(
                    opportunity,
                    "probability_of_profit",
                    None,
                )
                if opportunity is not None
                else None
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
            portfolio_position=position,
            metadata={
                "candidate_metadata":
                    dict(bundle.metadata),
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
