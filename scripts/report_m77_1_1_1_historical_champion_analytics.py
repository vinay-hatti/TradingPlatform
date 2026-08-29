from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_ai.database import SessionLocal
from trading_ai.historical_underlying_replay.analytics import HistoricalChampionAnalyticsService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="M77.1.1.1 read-only historical champion semantic-transparency analytics"
    )
    parser.add_argument("--replay-run-id")
    parser.add_argument("--output")
    args = parser.parse_args()

    with SessionLocal() as session:
        report = HistoricalChampionAnalyticsService(session).build_report(args.replay_run_id)

    rendered = json.dumps(report, default=str, indent=2)
    print("=== M77.1.1.1 HISTORICAL CHAMPION ANALYTICS ===")
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
