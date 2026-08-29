from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_ai.database import SessionLocal
from trading_ai.historical_underlying_replay.certification import (
    MultiYearFrozenChampionCertificationService,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="M77.2 read-only multi-year frozen-champion certification report"
    )
    parser.add_argument(
        "--manifest",
        default="reports/m77/m77_2_multiyear_frozen_champion_manifest.json",
    )
    parser.add_argument(
        "--output",
        default="reports/m77/m77_2_multiyear_frozen_champion_certification.json",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        raise SystemExit(f"Manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    run_ids = [
        item["replay_run_id"]
        for item in manifest.get("segments", [])
        if item.get("replay_run_id")
        and item.get("status") in {"READY", "DEGRADED"}
    ]
    if not run_ids:
        raise SystemExit("Manifest contains no completed replay_run_ids")

    with SessionLocal() as session:
        report = MultiYearFrozenChampionCertificationService(
            session
        ).build_report(run_ids)

    rendered = json.dumps(report, default=str, indent=2)
    print("=== M77.2 MULTI-YEAR FROZEN CHAMPION CERTIFICATION ===")
    print(rendered)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered + "\n")
    print(f"\nReport: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
