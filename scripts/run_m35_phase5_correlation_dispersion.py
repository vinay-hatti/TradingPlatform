from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_ai.scanner.correlation_dispersion.history_builder import (
    build_return_history,
)
from trading_ai.scanner.correlation_dispersion.reporting import (
    render_console_report,
)
from trading_ai.scanner.correlation_dispersion.serialization import (
    load_jsonl,
    write_json_atomic,
)
from trading_ai.scanner.correlation_dispersion.service import (
    CorrelationDispersionService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build Milestone 35 Phase 5 correlation and dispersion analytics."
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
        "--history-path",
        default=(
            "reports/m35/phase5/correlation_dispersion/"
            "return_history.jsonl"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="reports/m35/phase5/correlation_dispersion",
    )
    parser.add_argument(
        "--build-history",
        action="store_true",
    )
    parser.add_argument(
        "--lookback-rows",
        type=int,
        default=90,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    as_of_date = date.fromisoformat(args.as_of_date)

    if args.build_history:
        records = load_jsonl(args.input_path)
        symbols = sorted(
            {
                str(record["symbol"]).strip().upper()
                for record in records
                if record.get("symbol")
                and record.get("governance_status")
                in {"READY", "REVIEW"}
            }
        )
        build_return_history(
            symbols=symbols,
            as_of_date=as_of_date,
            lookback_rows=args.lookback_rows,
            output_path=args.history_path,
        )

    run_profile = CorrelationDispersionService().run(
        as_of_date=as_of_date,
        input_path=args.input_path,
        history_path=args.history_path,
        output_path=output_dir / "correlation_dispersion_profile.json",
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
