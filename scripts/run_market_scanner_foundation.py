from __future__ import annotations

import argparse
from uuid import uuid4

from trading_ai.research_workstation.scanner import (
    MarketCandidateProfile,
    MarketScanRequestProfile,
    MarketScannerService,
    ScannerFilterProfile,
)


def sample_candidates() -> list[MarketCandidateProfile]:
    return [
        MarketCandidateProfile(
            symbol="AAPL",
            price=225.0,
            average_volume=52_000_000,
            option_volume=1_200_000,
            open_interest=3_500_000,
            spread_pct=0.02,
            iv_rank=58.0,
            iv_percentile=66.0,
            atr_pct=2.2,
            trend_score=82.0,
            momentum_score=78.0,
            liquidity_score=98.0,
            volatility_score=72.0,
            regime_score=85.0,
            decision_confidence=84.0,
            expected_return=0.18,
            risk_score=31.0,
            reward_risk_ratio=3.2,
            signal="CALL",
            regime="TREND_UP",
        ),
        MarketCandidateProfile(
            symbol="MSFT",
            price=445.0,
            average_volume=24_000_000,
            option_volume=540_000,
            open_interest=1_850_000,
            spread_pct=0.025,
            iv_rank=49.0,
            iv_percentile=55.0,
            atr_pct=1.8,
            trend_score=76.0,
            momentum_score=72.0,
            liquidity_score=94.0,
            volatility_score=64.0,
            regime_score=78.0,
            decision_confidence=81.0,
            expected_return=0.15,
            risk_score=28.0,
            reward_risk_ratio=2.8,
            signal="CALL",
            regime="TREND_UP",
        ),
        MarketCandidateProfile(
            symbol="XYZ",
            price=8.0,
            average_volume=120_000,
            option_volume=10,
            open_interest=50,
            spread_pct=0.30,
            iv_rank=20.0,
            iv_percentile=22.0,
            atr_pct=0.5,
            trend_score=30.0,
            momentum_score=25.0,
            liquidity_score=8.0,
            volatility_score=25.0,
            regime_score=20.0,
            decision_confidence=35.0,
            expected_return=0.03,
            risk_score=88.0,
            reward_risk_ratio=0.6,
            signal="NEUTRAL",
            regime="CHOP",
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Milestone 34 scanner foundation.")
    parser.add_argument(
        "--output",
        default="reports/scans/m34_phase1_step1_sample.json",
    )
    args = parser.parse_args()

    candidates = sample_candidates()
    request = MarketScanRequestProfile(
        scan_id=f"scan-{uuid4().hex[:12]}",
        universe=tuple(candidate.symbol for candidate in candidates),
        filters=ScannerFilterProfile(
            min_price=20.0,
            min_average_volume=1_000_000,
            min_option_volume=1_000,
            min_open_interest=10_000,
            max_spread_pct=0.10,
            min_iv_rank=30.0,
            minimum_atr_pct=1.0,
            required_signals=("CALL", "PUT"),
        ),
        maximum_results=20,
        minimum_composite_score=50.0,
    )

    result = MarketScannerService().execute(
        request=request,
        candidates=candidates,
        output_path=args.output,
    )

    print("========== Institutional Market Scanner ==========")
    print(f"Scan ID        : {result.scan_id}")
    print(f"Universe       : {result.universe_size}")
    print(f"Evaluated      : {result.evaluated_count}")
    print(f"Rejected       : {result.rejected_count}")
    print(f"Ranked Results : {len(result.ranked_candidates)}")
    print("--------------------------------------------------")
    for candidate in result.ranked_candidates:
        print(
            f"{candidate.rank:>2}. {candidate.symbol:<6} "
            f"score={candidate.composite_score:>6.2f} "
            f"prob={candidate.probability_score:>6.2f} "
            f"edge={candidate.edge_score:>8.4f} "
            f"signal={candidate.signal:<5} "
            f"regime={candidate.regime}"
        )
    print(f"Report         : {args.output}")


if __name__ == "__main__":
    main()
