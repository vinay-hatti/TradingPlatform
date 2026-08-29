from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_ai.database import SessionLocal
from trading_ai.historical_underlying_replay.attribution import (
    ConditionalEdgeAttributionService,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="M77.3 read-only conditional edge attribution and historical regime authority"
    )
    parser.add_argument(
        "--manifest",
        default="reports/m77/certified/m77_2_multiyear_frozen_champion_manifest.json",
    )
    parser.add_argument(
        "--output",
        default="reports/m77/m77_3_conditional_edge_attribution.json",
    )
    parser.add_argument(
        "--regime-output",
        default="reports/m77/m77_3_historical_regime_authority.json",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        raise SystemExit(f"Certified M77.2 manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    if not (
        manifest.get("governance", {}).get("production_authority_effect") is False
        and manifest.get("governance", {}).get("production_model_mutation") is False
        and manifest.get("governance", {}).get("automatic_champion_promotion") is False
    ):
        raise SystemExit("M77.2 certified manifest governance is not fail-closed")
    run_ids = manifest.get("replay_run_ids") or []
    if not run_ids:
        raise SystemExit("Certified M77.2 manifest contains no replay_run_ids")

    with SessionLocal() as session:
        report = ConditionalEdgeAttributionService(session).build_report(run_ids)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, default=str, indent=2)
    output.write_text(rendered + "\n")

    regime_output = Path(args.regime_output)
    regime_output.parent.mkdir(parents=True, exist_ok=True)
    regime_output.write_text(
        json.dumps(
            {
                "regime_authority_version": report["regime_authority_version"],
                "governance": report["governance"],
                **report["historical_regime_authority"],
            },
            default=str,
            indent=2,
        ) + "\n"
    )

    print("=== M77.3 CONDITIONAL EDGE ATTRIBUTION ===")
    print(json.dumps({
        "coverage": report["coverage"],
        "candidate_summary": report["candidate_summary"],
        "regime_counts": report["historical_regime_authority"]["regime_counts"],
        "bearish_failure_attribution": report["bearish_failure_attribution"],
        "production_authority_effect": False,
    }, default=str, indent=2))
    print(f"Report: {output}")
    print(f"Regime authority: {regime_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
