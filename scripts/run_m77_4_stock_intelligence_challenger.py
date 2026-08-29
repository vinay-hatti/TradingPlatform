#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from trading_ai.database.session import SessionLocal
from trading_ai.historical_underlying_replay.challenger import (
    GovernedChallengerWalkForwardService,
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        default="reports/m77/certified/m77_2_multiyear_frozen_champion_manifest.json",
    )
    parser.add_argument(
        "--m77-3-attribution",
        default="reports/m77/m77_3_conditional_edge_attribution.json",
    )
    parser.add_argument(
        "--output",
        default="reports/m77/m77_4_walk_forward_challenger_certification.json",
    )
    parser.add_argument(
        "--policy-output",
        default="reports/m77/m77_4_research_challenger_policy.json",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    attribution_path = Path(args.m77_3_attribution)
    if not manifest_path.exists():
        raise RuntimeError(f"M77.2 certified manifest not found: {manifest_path}")
    if not attribution_path.exists():
        raise RuntimeError(f"M77.3 attribution artifact not found: {attribution_path}")

    manifest = json.loads(manifest_path.read_text())
    attribution = json.loads(attribution_path.read_text())
    if manifest.get("status") != "READY":
        raise RuntimeError("M77.2 manifest must be READY")
    if attribution.get("governance", {}).get("production_authority_effect") is not False:
        raise RuntimeError("M77.3 attribution governance is not research-isolated")

    replay_run_ids = list(manifest.get("replay_run_ids") or [])
    if not replay_run_ids:
        raise RuntimeError("M77.2 manifest contains no replay_run_ids")

    with SessionLocal() as session:
        report = GovernedChallengerWalkForwardService(session).build_report(
            replay_run_ids
        )

    report["lineage"] = {
        "m77_2_manifest": str(manifest_path),
        "m77_2_manifest_sha256": _sha256(manifest_path),
        "m77_3_attribution": str(attribution_path),
        "m77_3_attribution_sha256": _sha256(attribution_path),
        "m77_3_grades_used_for_holdout_selection": False,
        "replay_run_ids": replay_run_ids,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n")

    policy = {
        "challenger_version": report["challenger_version"],
        "governance": report["governance"],
        "lineage": report["lineage"],
        "summary": report["summary"],
        "challenger_policy": report["challenger_policy"],
    }
    policy_out = Path(args.policy_output)
    policy_out.parent.mkdir(parents=True, exist_ok=True)
    policy_out.write_text(json.dumps(policy, indent=2, default=str) + "\n")

    print(json.dumps({
        "status": "READY",
        "output": str(out),
        "policy_output": str(policy_out),
        "folds": report["summary"]["folds"],
        "research_challenger_eligible": report["summary"]["research_challenger_eligible"],
        "eligible_20d": report["summary"]["eligible_20d"],
        "eligible_60d": report["summary"]["eligible_60d"],
        "production_champion_change": False,
    }, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
