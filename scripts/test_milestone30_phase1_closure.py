from __future__ import annotations

import ast
from pathlib import Path


REQUIRED_MODULES = (
    "src/trading_ai/config/production_configuration.py",
    "src/trading_ai/config/production_runtime_policy.py",
    "src/trading_ai/config/production_runtime_profile.py",
    "src/trading_ai/config/production_runtime_engine.py",
    "src/trading_ai/config/production_runtime_service.py",
    "src/trading_ai/config/production_runtime_serialization.py",
    "src/trading_ai/config/secret_provider.py",
    "src/trading_ai/config/environment_profile.py",
    "src/trading_ai/config/environment_registry_policy.py",
    "src/trading_ai/config/environment_registry.py",
    "src/trading_ai/config/environment_promotion_engine.py",
    "src/trading_ai/config/environment_registry_service.py",
    "src/trading_ai/config/environment_registry_serialization.py",
    "src/trading_ai/config/secret_governance_policy.py",
    "src/trading_ai/config/secret_governance_profile.py",
    "src/trading_ai/config/secret_inventory_registry.py",
    "src/trading_ai/config/credential_health_engine.py",
    "src/trading_ai/config/secret_governance_service.py",
    "src/trading_ai/config/startup_readiness_policy.py",
    "src/trading_ai/config/startup_readiness_profile.py",
    "src/trading_ai/config/startup_readiness_engine.py",
    "src/trading_ai/config/startup_readiness_service.py",
    "src/trading_ai/config/production_readiness_reporting.py",
)

REQUIRED_COMMANDS = (
    "production-runtime-safety-test",
    "environment-registry-test",
    "secret-governance-test",
    "startup-readiness-check",
    "startup-readiness-test",
    "production-readiness-report",
    "milestone30-phase1-regression-test",
    "milestone30-phase1-closure-test",
)


def main() -> None:
    missing = [path for path in REQUIRED_MODULES if not Path(path).exists()]
    assert not missing, "Missing Phase 1 modules: " + ", ".join(missing)

    cli = Path("src/trading_ai/__main__.py")
    assert cli.exists(), "Active CLI file is missing."
    source = cli.read_text(encoding="utf-8")
    ast.parse(source)

    for command in REQUIRED_COMMANDS:
        assert command in source, f"Missing CLI command: {command}"

    report_source = Path(
        "src/trading_ai/config/production_readiness_reporting.py"
    ).read_text(encoding="utf-8")
    for heading in (
        "Startup Readiness Gate",
        "Runtime Safety Controls",
        "Environment Configuration Registry",
        "Credential Health and Rotation Governance",
        "Operational Diagnostics",
    ):
        assert heading in report_source, f"Missing report section: {heading}"

    print("All Milestone 30 Phase 1 closure assertions passed.")


if __name__ == "__main__":
    main()
