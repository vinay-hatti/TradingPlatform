from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.research_workstation.scanner import (
    MarketCandidateProfile,
    MarketScanRequestProfile,
    MarketScannerEngine,
    MarketScannerPolicy,
    MarketScannerService,
    ScannerFilterProfile,
)


def candidate(symbol: str, **overrides) -> MarketCandidateProfile:
    payload = {
        "symbol": symbol,
        "price": 100.0,
        "average_volume": 5_000_000,
        "option_volume": 50_000,
        "open_interest": 150_000,
        "spread_pct": 0.03,
        "iv_rank": 55.0,
        "iv_percentile": 60.0,
        "atr_pct": 2.0,
        "trend_score": 80.0,
        "momentum_score": 75.0,
        "liquidity_score": 90.0,
        "volatility_score": 70.0,
        "regime_score": 82.0,
        "decision_confidence": 84.0,
        "expected_return": 0.18,
        "risk_score": 30.0,
        "reward_risk_ratio": 3.0,
        "signal": "CALL",
        "regime": "TREND_UP",
    }
    payload.update(overrides)
    return MarketCandidateProfile(**payload)


def main() -> None:
    policy = MarketScannerPolicy()
    policy.validate()
    assert abs(
        sum(
            (
                policy.trend_weight,
                policy.momentum_weight,
                policy.liquidity_weight,
                policy.volatility_weight,
                policy.regime_weight,
                policy.probability_weight,
                policy.expected_return_weight,
                policy.reward_risk_weight,
            )
        )
        - 1.0
    ) < 1e-9

    request = MarketScanRequestProfile(
        scan_id="scanner-test",
        universe=("AAA", "BBB", "CCC"),
        filters=ScannerFilterProfile(
            min_price=20.0,
            min_average_volume=1_000_000,
            min_option_volume=1_000,
            min_open_interest=10_000,
            max_spread_pct=0.10,
            min_iv_rank=30.0,
            required_signals=("CALL", "PUT"),
        ),
        maximum_results=2,
        minimum_composite_score=40.0,
    )

    candidates = [
        candidate("AAA", decision_confidence=88.0, expected_return=0.20),
        candidate("BBB", decision_confidence=78.0, expected_return=0.14),
        candidate(
            "CCC",
            price=5.0,
            average_volume=100_000,
            option_volume=5,
            open_interest=25,
            spread_pct=0.40,
            iv_rank=10.0,
            signal="NEUTRAL",
        ),
    ]

    engine = MarketScannerEngine(policy)
    result = engine.scan(request, candidates)

    assert result.scan_id == "scanner-test"
    assert result.evaluated_count == 3
    assert result.rejected_count == 1
    assert len(result.ranked_candidates) == 2
    assert result.ranked_candidates[0].symbol == "AAA"
    assert result.ranked_candidates[0].rank == 1
    assert result.ranked_candidates[1].symbol == "BBB"

    with TemporaryDirectory() as directory:
        output = Path(directory) / "scan.json"
        persisted = MarketScannerService(engine).execute(
            request,
            candidates,
            output_path=output,
        )
        assert persisted.ranked_candidates
        assert output.exists()
        text = output.read_text(encoding="utf-8")
        assert '"scan_id": "scanner-test"' in text
        assert '"symbol": "AAA"' in text

    print("All Milestone 34 Phase 1 Step 1 market scanner assertions passed.")


if __name__ == "__main__":
    main()
