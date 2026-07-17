import argparse
import subprocess
import sys


def run_script(script, extra_args=None):

    cmd = [sys.executable, script]

    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(cmd)

    raise SystemExit(result.returncode)


def main():

    parser = argparse.ArgumentParser(
        description="Trading AI command line"
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("scan")
    sub.add_parser("optimize")
    sub.add_parser("dashboard")
    sub.add_parser("daily")
    sub.add_parser("option-details")
    sub.add_parser("option-rankings")
    sub.add_parser("backtest-smoke")
    sub.add_parser("backtest-engine-test")
    sub.add_parser("backtest-datasource-test")
    sub.add_parser("strategy-runner-test")
    sub.add_parser("trade-generator-test")
    sub.add_parser("backtest")
    sub.add_parser("position-sizer-test")
    sub.add_parser("backtest-experiments")
    sub.add_parser("analyze-experiments")
    sub.add_parser("walkforward-splitter-test")
    sub.add_parser("walkforward-optimizer-test")
    sub.add_parser("walkforward-validator-test")
    sub.add_parser("walkforward")
    sub.add_parser("analyze-walkforward")
    sub.add_parser("walkforward-report")
    sub.add_parser("black-scholes-test")
    sub.add_parser("analyze-greeks")
    sub.add_parser("score-strategies")
    sub.add_parser("optimization-report")
    sub.add_parser("profile-comparison")
    sub.add_parser("select-live-profile")
    sub.add_parser("show-live-profile")
    sub.add_parser("daily-scan")
    sub.add_parser("risk-metrics-test")
    sub.add_parser("show-risk-metrics")
    sub.add_parser("score-risk-aware")
    sub.add_parser("risk-optimization-report")
    sub.add_parser("import-option-chain")
    sub.add_parser("test-option-pricing")
    sub.add_parser("compare-option-pricing")
    sub.add_parser("volatility-test")
    sub.add_parser("strategy-selector-test")
    sub.add_parser("strike-optimizer-test")
    sub.add_parser("expiration-optimizer-test")
    sub.add_parser("expected-move-test")
    sub.add_parser("strategy-scoring-test")
    sub.add_parser("institutional-ranking-test")
    sub.add_parser("multi-strategy-test")
    sub.add_parser("portfolio-construction-test")
    sub.add_parser("institutional-decision-test")
    sub.add_parser("probability-engine-test")
    sub.add_parser("scenario-engine-test")
    sub.add_parser("distribution-risk-test")
    sub.add_parser("risk-surface-test")
    sub.add_parser("risk-surface-report-test")
    sub.add_parser("portfolio-risk-surface-test")
    sub.add_parser("phase4-regression-test")
    sub.add_parser("portfolio-optimization-test")
    sub.add_parser("portfolio-optimization-integration-test")
    sub.add_parser("portfolio-optimization-report-test")
    sub.add_parser("portfolio-optimization-frontier-test")
    sub.add_parser("portfolio-optimization-frontier-report-test")
    sub.add_parser("portfolio-optimization-recommendation-test")
    sub.add_parser("phase5-regression-test")
    sub.add_parser("probability-calibration-test")
    sub.add_parser("segmented-probability-calibration-test")
    sub.add_parser("probability-calibration-integration-test")
    sub.add_parser("probability-calibration-ranking-test")
    sub.add_parser("probability-calibration-report-test")
    sub.add_parser("probability-calibration-governance-test")
    sub.add_parser("phase6-regression-test")
    sub.add_parser("institutional-walk-forward-test")
    sub.add_parser("walk-forward-adapters-test")
    sub.add_parser("walk-forward-calibration-test")
    sub.add_parser("walk-forward-integration-test")
    sub.add_parser("walk-forward-report-test")
    sub.add_parser("walk-forward-governance-test")
    sub.add_parser("phase7-regression-test")
    sub.add_parser("market-regime-test")
    sub.add_parser("market-regime-forecast-test")
    sub.add_parser("market-breadth-test")
    sub.add_parser("market-regime-integration-test")
    sub.add_parser("market-regime-report-test")
    sub.add_parser("market-regime-governance-test")
    sub.add_parser("execution-analytics-test")
    sub.add_parser("execution-aggregation-test")
    sub.add_parser("execution-benchmark-routing-test")
    sub.add_parser("execution-integration-test")
    sub.add_parser("execution-report-test")
    sub.add_parser("execution-governance-test")
    sub.add_parser("execution-route-registry-test")
    sub.add_parser("execution-champion-challenger-test")
    sub.add_parser("execution-governance-integration-test")
    sub.add_parser("execution-governance-decision-contract-test")
    sub.add_parser("execution-governance-report-test")
    sub.add_parser("phase9-regression-test")
    sub.add_parser("phase9-closure-test")
    sub.add_parser("adaptive-strategy-test")
    sub.add_parser("strategy-learning-test")
    sub.add_parser("ensemble-decision-test")
    sub.add_parser("online-adaptation-test")
    sub.add_parser("phase10-decision-integration-test")
    sub.add_parser("phase10-decision-contract-test")
    sub.add_parser("phase10-report-test")
    sub.add_parser("phase10-cli-test")
    sub.add_parser("phase10-regression-test")
    sub.add_parser("phase10-closure-test")
    sub.add_parser("phase8-regression-test")

    sub.add_parser("production-runtime-safety-test")
    sub.add_parser("environment-registry-test")
    sub.add_parser("secret-governance-test")
    sub.add_parser("startup-readiness-check")
    sub.add_parser("startup-readiness-test")

    paper = sub.add_parser("paper")
    paper_sub = paper.add_subparsers(dest="paper_command")

    paper_sub.add_parser("run")
    paper_sub.add_parser("mark")
    paper_sub.add_parser("status")
    paper_sub.add_parser("reset")

    args, extra = parser.parse_known_args()

    if args.command == "scan":
        run_script("scripts/run_scanner.py", extra)

    elif args.command == "optimize":
        run_script("scripts/optimize_portfolio.py", extra)

    elif args.command == "dashboard":
        run_script("scripts/build_dashboard.py", extra)

    elif args.command == "daily":
        run_script("scripts/run_paper_daily.py", extra)

    elif args.command == "option-details":
        run_script("scripts/option_details.py", extra)

    elif args.command == "option-rankings":
        run_script("scripts/export_option_rankings.py", extra)

    elif args.command == "backtest-smoke":
        run_script("scripts/run_backtest_smoke.py", extra)

    elif args.command == "backtest-engine-test":
        run_script("scripts/test_backtest_engine.py", extra)

    elif args.command == "backtest-datasource-test":
        run_script("scripts/test_historical_datasource.py", extra)

    elif args.command == "strategy-runner-test":
        run_script("scripts/test_strategy_runner.py", extra)

    elif args.command == "trade-generator-test":
        run_script("scripts/test_trade_generator.py", extra)

    elif args.command == "backtest":
        run_script("scripts/run_historical_backtest.py", extra)

    elif args.command == "position-sizer-test":
        run_script("scripts/test_position_sizer.py", extra)

    elif args.command == "backtest-experiments":
        run_script("scripts/run_backtest_experiments.py", extra)

    elif args.command == "analyze-experiments":
        run_script("scripts/analyze_experiments.py", extra)

    elif args.command == "walkforward-splitter-test":
        run_script("scripts/test_walkforward_splitter.py", extra)

    elif args.command == "walkforward-optimizer-test":
        run_script(
            "scripts/test_walkforward_optimizer.py",
            extra,
        )

    elif args.command == "walkforward-validator-test":
        run_script("scripts/test_walkforward_validator.py", extra)

    elif args.command == "walkforward":
        run_script("scripts/run_walkforward.py", extra)

    elif args.command == "analyze-walkforward":
        run_script("scripts/analyze_walkforward.py", extra)

    elif args.command == "walkforward-report":
        run_script("scripts/build_walkforward_report.py", extra)

    elif args.command == "black-scholes-test":
        run_script("scripts/test_black_scholes.py", extra)

    elif args.command == "analyze-greeks":
        run_script("scripts/analyze_greeks.py", extra)

    elif args.command == "score-strategies":
        run_script("scripts/score_strategies.py", extra)

    elif args.command == "optimization-report":
        run_script("scripts/build_optimization_report.py", extra)

    elif args.command == "profile-comparison":
        run_script(
            "scripts/build_profile_comparison_report.py",
            extra,
        )

    elif args.command == "select-live-profile":
        run_script("scripts/select_live_profile.py", extra)

    elif args.command == "show-live-profile":
        run_script("scripts/show_live_profile.py", extra)

    elif args.command == "daily-scan":
        run_script("scripts/run_daily_scan.py", extra)

    elif args.command == "risk-metrics-test":
        run_script("scripts/test_risk_metrics.py", extra)

    elif args.command == "show-risk-metrics":
        run_script("scripts/show_risk_metrics.py", extra)

    elif args.command == "score-risk-aware":
        run_script("scripts/score_risk_aware_strategies.py", extra)

    elif args.command == "risk-optimization-report":
        run_script("scripts/risk_optimization_report.py", extra)

    elif args.command == "import-option-chain":
        run_script("scripts/import_option_chain.py", extra)

    elif args.command == "test-option-pricing":
        run_script("scripts/test_option_pricing_service.py", extra)

    elif args.command == "compare-option-pricing":
        run_script("scripts/compare_option_pricing_sources.py", extra)

    elif args.command == "volatility-test":
        run_script("scripts/test_volatility_engine.py", extra)

    elif args.command == "strategy-selector-test":
        run_script("scripts/test_strategy_selector.py", extra)

    elif args.command == "strike-optimizer-test":
        run_script("scripts/test_strike_optimizer.py", extra)

    elif args.command == "expiration-optimizer-test":
        run_script("scripts/test_expiration_optimizer.py", extra)

    elif args.command == "expected-move-test":
        run_script("scripts/test_expected_move_engine.py", extra)

    elif args.command == "strategy-scoring-test":
        run_script("scripts/test_strategy_scoring_engine.py", extra)

    elif args.command == "institutional-ranking-test":
        run_script("scripts/test_institutional_ranking_engine.py", extra)

    elif args.command == "multi-strategy-test":
        run_script("scripts/test_multi_strategy_support.py", extra)

    elif args.command == "portfolio-construction-test":
        run_script("scripts/test_portfolio_construction.py", extra)

    elif args.command == "institutional-decision-test":
        run_script("scripts/test_institutional_decision_engine.py", extra)

    elif args.command == "probability-engine-test":
        run_script("scripts/test_probability_engine.py", extra)

    elif args.command == "scenario-engine-test":
        run_script("scripts/test_scenario_engine.py", extra)

    elif args.command == "distribution-risk-test": 
        run_script("scripts/test_distribution_risk_engine.py", extra)

    elif args.command == "risk-surface-test":
        run_script("scripts/test_risk_surface_engine.py", extra)

    elif args.command == "risk-surface-report-test":
        run_script("scripts/test_risk_surface_reporting.py", extra)

    elif args.command == "portfolio-risk-surface-test":
        run_script("scripts/test_portfolio_risk_surface.py", extra)

    elif args.command == "phase4-regression-test":
        run_script("scripts/test_phase4_regression.py", extra)

    elif args.command == "portfolio-optimization-test":
        run_script("scripts/test_portfolio_optimization.py", extra)

    elif args.command == "portfolio-optimization-integration-test":
        run_script("scripts/test_portfolio_optimization_integration.py", extra)

    elif args.command == "portfolio-optimization-report-test":
        run_script("scripts/test_portfolio_optimization_reporting.py", extra)

    elif args.command == "portfolio-optimization-frontier-test":
        run_script("scripts/test_portfolio_optimization_frontier.py", extra)

    elif args.command == "portfolio-optimization-frontier-report-test":
        run_script("scripts/test_portfolio_optimization_frontier_reporting.py", extra)

    elif args.command == "portfolio-optimization-recommendation-test":
        run_script("scripts/test_portfolio_optimization_recommendation.py", extra)

    elif args.command == "phase5-regression-test":
        run_script("scripts/test_phase5_regression.py", extra)

    elif args.command == "probability-calibration-test":
        run_script("scripts/test_probability_calibration.py", extra)

    elif args.command == "segmented-probability-calibration-test":
        run_script("scripts/test_segmented_probability_calibration.py", extra)

    elif args.command == "probability-calibration-integration-test":
        run_script("scripts/test_probability_calibration_integration.py", extra)

    elif args.command == "probability-calibration-ranking-test":
        run_script("scripts/test_probability_calibration_ranking.py", extra)

    elif args.command == "probability-calibration-report-test":
        run_script("scripts/test_probability_calibration_reporting.py", extra)

    elif args.command == "probability-calibration-governance-test":
        run_script("scripts/test_probability_calibration_governance.py", extra)

    elif args.command == "phase6-regression-test":
        run_script("scripts/test_phase6_regression.py", extra)


    elif args.command == "institutional-walk-forward-test":
        run_script("scripts/test_institutional_walk_forward.py", extra)

    elif args.command == "walk-forward-adapters-test":
        run_script("scripts/test_walk_forward_adapters.py", extra)

    elif args.command == "walk-forward-integration-test":
        run_script("scripts/test_walk_forward_integration.py", extra)

    elif args.command == "walk-forward-report-test":
        run_script("scripts/test_walk_forward_reporting.py", extra)

    elif args.command == "walk-forward-calibration-test":
        run_script("scripts/test_walk_forward_probability_calibration.py", extra)

    elif args.command == "walk-forward-governance-test":
        run_script("scripts/test_walk_forward_governance.py", extra)

    elif args.command == "phase7-regression-test":
        run_script("scripts/test_phase7_regression.py", extra)

    elif args.command == "market-regime-test":
        run_script("scripts/test_market_regime_engine.py", extra)

    elif args.command == "market-regime-forecast-test":
        run_script("scripts/test_market_regime_forecast.py", extra)

    elif args.command == "market-breadth-test":
        run_script("scripts/test_market_breadth_engine.py", extra)

    elif args.command == "market-regime-integration-test":
        run_script("scripts/test_market_regime_integration.py", extra)

    elif args.command == "market-regime-report-test":
        run_script("scripts/test_market_regime_reporting.py", extra)

    elif args.command == "market-regime-governance-test":
        run_script("scripts/test_market_regime_governance.py", extra)

    elif args.command == "phase8-regression-test":
        run_script("scripts/test_phase8_regression.py", extra)


    elif args.command == "execution-analytics-test":
        run_script("scripts/test_execution_analytics.py", extra)

    elif args.command == "execution-aggregation-test":
        run_script("scripts/test_execution_aggregation.py", extra)

    elif args.command == "execution-benchmark-routing-test":
        run_script("scripts/test_execution_benchmark_routing.py", extra)

    elif args.command == "execution-integration-test":
        run_script("scripts/test_execution_integration.py", extra)

    elif args.command == "execution-report-test":
        run_script("scripts/test_execution_reporting.py", extra)

    elif args.command == "execution-governance-test":
        run_script("scripts/test_execution_governance.py", extra)

    elif args.command == "execution-route-registry-test":
        run_script("scripts/test_execution_route_registry.py", extra)

    elif args.command == "execution-champion-challenger-test":
        run_script("scripts/test_execution_champion_challenger.py", extra)

    elif args.command == "execution-governance-integration-test":
        run_script("scripts/test_execution_governance_integration.py", extra)

    elif args.command == "execution-governance-decision-contract-test":
        run_script("scripts/test_execution_governance_decision_contract.py", extra)

    elif args.command == "execution-governance-report-test":
        run_script("scripts/test_execution_governance_reporting.py", extra)

    elif args.command == "phase9-regression-test":
        run_script("scripts/test_phase9_regression.py", extra)

    elif args.command == "phase9-closure-test":
        run_script("scripts/test_phase9_closure.py", extra)

    elif args.command == "adaptive-strategy-test":
        run_script("scripts/test_adaptive_strategy_foundation.py", extra)

    elif args.command == "strategy-learning-test":
        run_script("scripts/test_strategy_learning.py", extra)

    elif args.command == "ensemble-decision-test":
        run_script("scripts/test_ensemble_decision.py", extra)

    elif args.command == "online-adaptation-test":
        run_script("scripts/test_online_adaptation.py", extra)

    elif args.command == "phase10-decision-integration-test":
        run_script("scripts/test_phase10_decision_integration.py", extra)

    elif args.command == "phase10-decision-contract-test":
        run_script("scripts/test_phase10_decision_contract.py", extra)

    elif args.command == "phase10-report-test":
        run_script("scripts/test_phase10_reporting.py", extra)

    elif args.command == "phase10-cli-test":
        run_script("scripts/test_phase10_cli.py", extra)

    elif args.command == "phase10-regression-test":
        run_script("scripts/test_phase10_regression.py", extra)

    elif args.command == "phase10-closure-test":
        run_script("scripts/test_phase10_closure.py", extra)


    elif args.command == "production-runtime-safety-test":
        run_script("scripts/test_production_runtime_safety.py", extra)

    elif args.command == "environment-registry-test":
        run_script("scripts/test_environment_configuration_registry.py", extra)

    elif args.command == "secret-governance-test":
        run_script("scripts/test_secret_governance.py", extra)

    elif args.command == "startup-readiness-check":
        run_script("scripts/run_startup_readiness_check.py", extra)

    elif args.command == "startup-readiness-test":
        run_script("scripts/test_startup_readiness_gate.py", extra)

    elif args.command == "paper":

        if args.paper_command == "run":
            run_script("scripts/paper_trade_from_optimizer.py", extra)

        elif args.paper_command == "mark":
            run_script("scripts/mark_paper_positions.py", extra)

        elif args.paper_command == "status":
            run_script("scripts/paper_status.py", extra)

        elif args.paper_command == "reset":
            run_script("scripts/reset_paper.py", extra)

        else:
            parser.print_help()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
