from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="M77.3 concise candidate-edge report")
    parser.add_argument(
        "--input",
        default="reports/m77/m77_3_conditional_edge_attribution.json",
    )
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()
    path = Path(args.input)
    if not path.exists():
        raise SystemExit(f"M77.3 attribution report not found: {path}")
    data = json.loads(path.read_text())
    print("=== M77.3 CONDITIONAL EDGE CERTIFICATION SUMMARY ===")
    print(json.dumps({
        "coverage": data["coverage"],
        "candidate_summary": data["candidate_summary"],
        "regime_counts": data["historical_regime_authority"]["regime_counts"],
        "bearish_failure_attribution": data["bearish_failure_attribution"],
    }, indent=2))
    print("\n--- TOP SUPPORTED CANDIDATES ---")
    shown = 0
    for item in data["candidate_registry"]:
        if item["evidence_grade"] not in {"A", "B"}:
            continue
        print(json.dumps({
            "candidate_id": item["candidate_id"],
            "horizon": item["horizon"],
            "grade": item["evidence_grade"],
            "status": item["certification_status"],
            "raw_n": item["raw_observations"],
            "nonoverlap_n": item["non_overlapping_observations"],
            "nonoverlap_return": item["nonoverlap_thesis_return_avg_pct"],
            "nonoverlap_hit": item["nonoverlap_directional_hit_rate_pct"],
            "positive_years": item["year_persistence"]["positive_years"],
            "qualified_years": item["year_persistence"]["qualified_years"],
            "positive_symbol_rate": item["symbol_breadth"]["positive_symbol_rate_pct"],
            "matched_excess": item["matched_control"]["matched_excess_thesis_return_avg_pct"],
            "dimensions": item["dimensions"],
        }, default=str))
        shown += 1
        if shown >= args.top:
            break
    if shown == 0:
        print("No Grade A/B candidates. This is a valid fail-closed result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
