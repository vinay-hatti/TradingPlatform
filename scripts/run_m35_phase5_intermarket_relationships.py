from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_ai.scanner.intermarket_relationships.reporting import (
    render_console_report,
)
from trading_ai.scanner.intermarket_relationships.serialization import (
    write_json_atomic,
)
from trading_ai.scanner.intermarket_relationships.service import (
    IntermarketRelationshipService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build Milestone 35 Phase 5 intermarket relationship analytics."
        )
    )
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument(
        "--input-path",
        default=(
            "reports/m35/phase5/cross_asset_data_foundation/"
            "cross_asset_features.jsonl"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="reports/m35/phase5/intermarket_relationships",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_profile = IntermarketRelationshipService().run(
        as_of_date=date.fromisoformat(args.as_of_date),
        input_path=args.input_path,
        output_path=output_dir / "intermarket_profile.json",
    )

    run_path = write_json_atomic(
        output_dir / "run.json",
        run_profile,
    )

    print(render_console_report(run_profile))
    print(f"Run report          : {run_path}")

    if run_profile.governance_status == "EXCLUDED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
