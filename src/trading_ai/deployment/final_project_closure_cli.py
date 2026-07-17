from __future__ import annotations

import argparse
import json
from pathlib import Path


def _inspect(args):
    payload = json.loads(
        Path(args.result).read_text(encoding="utf-8")
    )
    ready = bool(payload.get("ready_for_production"))
    print(
        "Final production readiness: "
        + ("READY" if ready else "BLOCKED")
    )
    return 0 if ready else 1


def register_final_project_closure_commands(subparsers):
    parser = subparsers.add_parser(
        "final-project-closure",
        help="Inspect final project closure results.",
    )
    parser.add_argument("--result", required=True)
    parser.set_defaults(func=_inspect)


def main(argv=None):
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="command", required=True)
    register_final_project_closure_commands(subs)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
