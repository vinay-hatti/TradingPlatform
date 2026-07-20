from __future__ import annotations

import argparse
import subprocess
import sys


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Milestone 34 Phase 5 complete reporting pipeline.")
    parser.add_argument("--knowledge-base-json", default="reports/m34/phase5/research_knowledge_base.json")
    parser.add_argument("--output-dir", default="reports/m34/phase5")
    args = parser.parse_args()

    python = sys.executable
    run([
        python,
        "scripts/run_m34_phase5_pattern_discovery.py",
        "--knowledge-base-json",
        args.knowledge_base_json,
        "--output-dir",
        args.output_dir,
    ])
    run([
        python,
        "scripts/run_m34_phase5_institutional_learning.py",
        "--knowledge-base-json",
        args.knowledge_base_json,
        "--output-dir",
        args.output_dir,
    ])
    run([
        python,
        "scripts/run_m34_phase5_analyst_performance.py",
        "--knowledge-base-json",
        args.knowledge_base_json,
        "--output-dir",
        args.output_dir,
    ])
    run([
        python,
        "scripts/run_m34_phase5_knowledge_dashboard.py",
        "--knowledge-base-json",
        args.knowledge_base_json,
        "--pattern-discovery-json",
        f"{args.output_dir}/pattern_discovery.json",
        "--institutional-learning-json",
        f"{args.output_dir}/institutional_learning.json",
        "--analyst-performance-json",
        f"{args.output_dir}/analyst_performance.json",
        "--output-dir",
        f"{args.output_dir}/dashboard",
    ])
    print("Milestone 34 Phase 5 complete pipeline finished successfully.")


if __name__ == "__main__":
    main()
