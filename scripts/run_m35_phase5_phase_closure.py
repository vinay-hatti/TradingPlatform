from __future__ import annotations

import argparse

from trading_ai.scanner.cross_asset_intelligence.phase_closure import (
    validate_phase5_artifacts,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Milestone 35 Phase 5 closure artifacts."
    )
    parser.add_argument(
        "--step1",
        default=(
            "reports/m35/phase5/cross_asset_data_foundation/"
            "cross_asset_features.jsonl"
        ),
    )
    parser.add_argument(
        "--step2",
        default=(
            "reports/m35/phase5/intermarket_relationships/"
            "intermarket_profile.json"
        ),
    )
    parser.add_argument(
        "--step3",
        default=(
            "reports/m35/phase5/sector_leadership_rotation/"
            "sector_leadership_profile.json"
        ),
    )
    parser.add_argument(
        "--step4",
        default=(
            "reports/m35/phase5/correlation_dispersion/"
            "correlation_dispersion_profile.json"
        ),
    )
    parser.add_argument(
        "--step5",
        default=(
            "reports/m35/phase5/cross_asset_intelligence/"
            "cross_asset_intelligence_profile.json"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = validate_phase5_artifacts(
        cross_asset_feature_path=args.step1,
        intermarket_path=args.step2,
        sector_path=args.step3,
        correlation_path=args.step4,
        intelligence_path=args.step5,
    )

    for assertion in result.assertions:
        print(f"PASS: {assertion}")
    for failure in result.failures:
        print(f"FAIL: {failure}")

    if not result.passed:
        raise SystemExit(1)

    print("Milestone 35 Phase 5 closure assertions passed.")


if __name__ == "__main__":
    main()
