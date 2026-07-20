from __future__ import annotations

import argparse
import json
from pathlib import Path

from .m32_runbook_catalog_service import OperationalRunbookCatalogService


def _inspect(args) -> int:
    payload = json.loads(Path(args.result).read_text(encoding="utf-8"))
    certified = bool(payload.get("certified"))
    decision = payload.get("certification_decision", "UNKNOWN")
    print(f"Milestone 32 certification: {decision}")
    print(f"Overall score: {float(payload.get('overall_score', 0.0)):.4f}")
    return 0 if certified else 1


def _generate_runbooks(args) -> int:
    generated = OperationalRunbookCatalogService().write_standard_runbooks(
        args.output
    )
    print(f"Generated {len(generated)} operational runbooks in {args.output}")
    for path in generated:
        print(path)
    return 0


def register_m32_phase5_commands(subparsers) -> None:
    parser = subparsers.add_parser(
        "m32-phase5",
        help="Milestone 32 Phase 5 certification and runbook utilities.",
    )
    commands = parser.add_subparsers(dest="phase5_command", required=True)

    inspect_parser = commands.add_parser(
        "inspect",
        help="Inspect a Milestone 32 certification JSON result.",
    )
    inspect_parser.add_argument("--result", required=True)
    inspect_parser.set_defaults(func=_inspect)

    runbook_parser = commands.add_parser(
        "generate-runbooks",
        help="Generate standard production operational runbooks.",
    )
    runbook_parser.add_argument(
        "--output",
        default="reports/runbooks/milestone32",
    )
    runbook_parser.set_defaults(func=_generate_runbooks)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_m32_phase5_commands(subparsers)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
