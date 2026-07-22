from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_ai.scanner.cross_asset_intelligence.reporting import (
    render_console_report,
    write_html_report,
)
from trading_ai.scanner.cross_asset_intelligence.serialization import (
    load_json,
    write_json_atomic,
)
from trading_ai.scanner.cross_asset_intelligence.service import (
    CrossAssetIntelligenceService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Consolidate Milestone 35 Phase 5 cross-asset intelligence "
            "and generate decision adjustments."
        )
    )
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument(
        "--intermarket-input",
        default=(
            "reports/m35/phase5/intermarket_relationships/"
            "intermarket_profile.json"
        ),
    )
    parser.add_argument(
        "--sector-input",
        default=(
            "reports/m35/phase5/sector_leadership_rotation/"
            "sector_leadership_profile.json"
        ),
    )
    parser.add_argument(
        "--correlation-input",
        default=(
            "reports/m35/phase5/correlation_dispersion/"
            "correlation_dispersion_profile.json"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="reports/m35/phase5/cross_asset_intelligence",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "cross_asset_intelligence_profile.json"

    run_profile = CrossAssetIntelligenceService().run(
        as_of_date=date.fromisoformat(args.as_of_date),
        intermarket_input_path=args.intermarket_input,
        sector_input_path=args.sector_input,
        correlation_input_path=args.correlation_input,
        output_path=output_path,
    )

    profile = load_json(output_path)
    from trading_ai.scanner.cross_asset_intelligence.engine import (
        CrossAssetIntelligenceEngine,
    )
    rebuilt = CrossAssetIntelligenceEngine().evaluate(
        as_of_date=date.fromisoformat(args.as_of_date),
        intermarket_profile=load_json(args.intermarket_input),
        sector_profile=load_json(args.sector_input),
        correlation_profile=load_json(args.correlation_input),
    )

    html_path = write_html_report(
        output_dir / "cross_asset_intelligence_report.html",
        rebuilt,
    )
    run_path = write_json_atomic(
        output_dir / "run.json",
        run_profile,
    )

    print(render_console_report(run_profile))
    print(f"HTML report        : {html_path}")
    print(f"Run report         : {run_path}")

    if run_profile.governance_status == "EXCLUDED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
