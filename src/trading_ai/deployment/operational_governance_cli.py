from __future__ import annotations

import argparse
import json
from pathlib import Path


def _inspect(args):
    path = Path(args.result)
    payload = json.loads(path.read_text(encoding="utf-8"))
    ready = (
        payload.get("recommendation")
        == "PRODUCTION_GOVERNANCE_READY"
    )
    print(
        "Operational governance readiness: "
        + ("READY" if ready else "BLOCKED")
    )
    return 0 if ready else 1


def register_operational_governance_commands(subparsers):
    parser = subparsers.add_parser(
        "operational-governance",
        help="Inspect operational-governance results.",
    )
    parser.add_argument("--result", required=True)
    parser.set_defaults(func=_inspect)


def main(argv=None):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )
    register_operational_governance_commands(subparsers)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
