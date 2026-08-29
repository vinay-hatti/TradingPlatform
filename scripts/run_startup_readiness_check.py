from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_ai.config.startup_readiness_serialization import dump, dumps
from trading_ai.config.startup_readiness_service import StartupReadinessService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the institutional startup readiness gate."
    )
    parser.add_argument("--environment", default=None)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--base-file", default="config/runtime.json")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--allow-blocked-exit-zero",
        action="store_true",
        help="Return exit code 0 even when startup is blocked.",
    )
    args = parser.parse_args()

    profile = StartupReadinessService(
        project_root=Path(args.project_root),
    ).evaluate(
        environment=args.environment,
        base_file=args.base_file,
    )

    if args.output:
        dump(profile, args.output)

    if args.json_output:
        print(dumps(profile))
    else:
        print("========== Startup Readiness ==========")
        print(f"Environment : {profile.environment}")
        print(f"Allowed     : {'YES' if profile.allowed else 'NO'}")
        print(f"Score       : {profile.score:.2f}")
        print(f"Grade       : {profile.grade}")
        print(f"Severity    : {profile.severity}")
        print(f"Version     : {profile.active_environment_version or 'N/A'}")
        print(f"Runtime     : {profile.runtime_score:.2f}")
        print(f"Environment : {profile.environment_score:.2f}")
        print(f"Secrets     : {profile.secret_score:.2f}")
        print(f"Decision    : {profile.recommendation}")
        if profile.rejection_reasons:
            print("Rejections  : " + ", ".join(profile.rejection_reasons))
        if profile.warnings:
            print("Warnings    : " + ", ".join(profile.warnings))
        print("=======================================")

    if not profile.allowed and not args.allow_blocked_exit_zero:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
