from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_ai.replay import HistoricalReplayService, ReplayPolicy, ReplaySelector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay a persisted scanner/decision lineage run.")
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--scanner-run-id")
    selector.add_argument("--decision-run-id")
    selector.add_argument("--ingestion-run-id")
    selector.add_argument("--publication-name")
    parser.add_argument("--mode", choices=["snapshot", "execute"], default="snapshot")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--allow-missing-decisions", action="store_true", default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selector = ReplaySelector(
        scanner_run_id=args.scanner_run_id,
        decision_run_id=args.decision_run_id,
        ingestion_run_id=args.ingestion_run_id,
        publication_name=args.publication_name,
    )
    policy = ReplayPolicy(
        allow_missing_decisions=bool(args.allow_missing_decisions),
        persist_replay=not args.no_persist,
    )
    service = HistoricalReplayService(policy=policy)
    result = service.run(selector, mode=args.mode)
    output_dir = Path(args.output_dir or f"reports/m47/replay/{date.today().isoformat()}/{result.replay_run_id}")
    paths = service.export(result, output_dir)

    print()
    print("========== Historical Replay ==========")
    print(f"Replay Run       : {result.replay_run_id}")
    print(f"Mode             : {result.mode}")
    print(f"Status           : {result.status}")
    print(f"Source Scanner   : {result.source.scanner_run_id or 'none'}")
    print(f"Source Decision  : {result.source.decision_run_id or 'none'}")
    print(f"Publication      : {result.source.publication_name or 'unknown'}")
    print(f"Ingestion Run    : {result.source.ingestion_run_id or 'unknown'}")
    print(f"Option Snapshot  : {result.source.option_snapshot_id or 'unknown'}")
    print(f"Candidates       : {len(result.replay_candidates)}")
    print(f"Decisions        : {len(result.replay_decisions)}")
    print(f"Comparisons      : {len(result.comparisons)}")
    print(f"Mismatches       : {result.metadata.get('mismatch_count', 0)}")
    print(f"JSON             : {paths['json']}")
    print(f"Manifest         : {paths['manifest']}")
    print("=======================================")
    print()
    return 0 if result.status == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
