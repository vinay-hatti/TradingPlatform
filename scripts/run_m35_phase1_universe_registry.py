from __future__ import annotations

import argparse
from pathlib import Path

from trading_ai.scanner.universe_management import (
    UniverseEngine,
    UniversePolicy,
    UniverseService,
    write_universe_json,
    write_universe_summary,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the governed Milestone 35 scanner universe."
    )
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-dir", default="reports/m35/phase1")
    parser.add_argument("--minimum-symbol-count", type=int, default=6000)
    parser.add_argument("--universe-id", default="US-LISTED-PRIMARY")
    parser.add_argument("--name", default="US Listed Equity and ETF Universe")
    args = parser.parse_args()

    policy = UniversePolicy(minimum_symbol_count=args.minimum_symbol_count)
    service = UniverseService(UniverseEngine(policy))
    result = service.build_from_csv(
        args.input_csv,
        universe_id=args.universe_id,
        name=args.name,
    )

    output_dir = Path(args.output_dir)
    full_path = write_universe_json(result, output_dir / "universe_registry.json")
    summary_path = write_universe_summary(result, output_dir / "universe_summary.json")

    print("Milestone 35 Phase 1 Step 1 universe registry completed.")
    print(f"Received: {result.received_count}")
    print(f"Accepted: {result.accepted_count}")
    print(f"Rejected: {result.rejected_count}")
    print(f"Duplicates: {result.duplicate_count}")
    print(f"Governance status: {result.universe.governance_status}")
    print(f"Registry: {full_path}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
