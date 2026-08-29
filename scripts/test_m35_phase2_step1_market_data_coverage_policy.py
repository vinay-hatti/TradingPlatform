from trading_ai.scanner.market_data_quality import CoverageStatus, MarketDataCoveragePolicy


def profiles(policy: MarketDataCoveragePolicy, ready: int, short: int, missing: int):
    result = []
    for index in range(ready):
        result.append(policy.build_symbol_profile(symbol=f"R{index}", row_count=300, trading_day_count=300))
    for index in range(short):
        result.append(policy.build_symbol_profile(symbol=f"S{index}", row_count=100, trading_day_count=100))
    for index in range(missing):
        result.append(policy.build_symbol_profile(symbol=f"M{index}", row_count=0, trading_day_count=0))
    return result


def main() -> None:
    policy = MarketDataCoveragePolicy(
        minimum_history_days=252,
        ready_coverage_percentage=99,
        degraded_coverage_percentage=95,
        review_coverage_percentage=80,
        ready_minimum_history_percentage=95,
        degraded_minimum_history_percentage=90,
    )

    assert policy.evaluate(profiles(policy, 100, 0, 0)).status is CoverageStatus.READY
    assert policy.evaluate(profiles(policy, 94, 4, 2)).status is CoverageStatus.DEGRADED
    assert policy.evaluate(profiles(policy, 79, 11, 10)).status is CoverageStatus.REVIEW
    assert policy.evaluate(profiles(policy, 69, 10, 21)).status is CoverageStatus.FAILED
    assert policy.evaluate([]).status is CoverageStatus.FAILED

    minimum_history_degraded = policy.evaluate(profiles(policy, 94, 6, 0))
    assert minimum_history_degraded.status is CoverageStatus.DEGRADED
    assert "MINIMUM_HISTORY_BELOW_READY_THRESHOLD" in minimum_history_degraded.reasons

    print("Milestone 35 Phase 2 Step 1 coverage policy assertions passed.")


if __name__ == "__main__":
    main()
