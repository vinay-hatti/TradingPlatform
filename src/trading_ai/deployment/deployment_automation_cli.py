from __future__ import annotations
import argparse
from datetime import datetime, timezone
from .deployment_adapter import InMemoryDeploymentAdapter, DeploymentTargetState
from .deployment_automation_profile import DeploymentStrategy
from .deployment_orchestrator import DeploymentOrchestrator
from .release_contract import ReleaseContract

def _demo(args):
    adapter = InMemoryDeploymentAdapter()
    adapter.seed(DeploymentTargetState(
        environment=args.environment.upper(), active_slot="blue",
        candidate_slot=None, traffic_percent=100,
        active_version=args.previous_version, candidate_version=None
    ))
    release = ReleaseContract(
        release_id=f"release-{args.version}",
        version=args.version,
        git_commit="cli",
        build_timestamp=datetime.now(timezone.utc).isoformat(),
        artifact_checksum="a"*64,
        artifact_location=args.artifact,
        migration_version="current",
        configuration_version="current",
        deployment_targets=(args.environment.upper(),),
        release_tag=f"v{args.version}",
        artifact_signed=True,
    )
    result = DeploymentOrchestrator(adapter=adapter).deploy(
        deployment_id=args.deployment_id, release=release,
        environment=args.environment,
        strategy=DeploymentStrategy(args.strategy),
        operator=args.operator,
    )
    print(f"Deployment status: {result.status}")
    return 0 if result.status == "COMPLETED" else 1

def register_deployment_automation_commands(subparsers):
    parser = subparsers.add_parser("deployment-automation")
    parser.add_argument("--deployment-id", required=True)
    parser.add_argument("--environment", default="STAGING")
    parser.add_argument("--strategy", choices=[x.value for x in DeploymentStrategy], default="BLUE_GREEN")
    parser.add_argument("--version", required=True)
    parser.add_argument("--previous-version", default="0.0.0")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--operator", default="cli")
    parser.set_defaults(func=_demo)

def main(argv=None):
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="command", required=True)
    register_deployment_automation_commands(subs)
    args = parser.parse_args(argv)
    return int(args.func(args))

if __name__ == "__main__":
    raise SystemExit(main())
