from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_ai.certification import CertificationPolicy, Milestone47CertificationService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Milestone 47 end-to-end operational certification.")
    parser.add_argument("--manifest", action="append", default=[], help="Report manifest to validate; may be repeated.")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--expected-alembic-head", default="m47_002")
    parser.add_argument("--require-decision-lineage", action="store_true")
    parser.add_argument("--require-replay-history", action="store_true")
    parser.add_argument("--allow-no-manifests", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    policy = CertificationPolicy(
        expected_alembic_head=args.expected_alembic_head,
        require_decision_lineage=bool(args.require_decision_lineage),
        require_replay_history=bool(args.require_replay_history),
        require_manifest_integrity=not args.allow_no_manifests,
    )
    service = Milestone47CertificationService(policy=policy)
    result = service.run(report_manifest_paths=args.manifest)
    output_dir = Path(args.output_dir or f"reports/m47/certification/{date.today().isoformat()}/{result.certification_run_id}")
    paths = service.export(result, output_dir)

    print("\n========== Milestone 47 Certification ==========")
    print(f"Certification Run : {result.certification_run_id}")
    print(f"Status            : {result.status}")
    print(f"Checks            : {result.metadata.get('check_count')}")
    print(f"Passed            : {result.metadata.get('passed_count')}")
    print(f"Failed            : {result.metadata.get('failed_count')}")
    print(f"Blocking Failures : {result.metadata.get('blocking_failure_count')}")
    for check in result.checks:
        print(f"[{check.status:6}] {check.code:28} {check.message}")
    print(f"JSON              : {paths['json']}")
    print(f"HTML              : {paths['html']}")
    print(f"Manifest          : {paths['manifest']}")
    print("================================================\n")
    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
