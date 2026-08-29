from __future__ import annotations

import tempfile
from pathlib import Path

from trading_ai.config.production_readiness_reporting import (
    ProductionReadinessReport,
)
from trading_ai.config.startup_readiness_engine import StartupReadinessEngine


def main() -> None:
    profile = StartupReadinessEngine().evaluate(
        environment="production",
        configuration_fingerprint="fingerprint-123",
        runtime_profile={
            "allowed": True,
            "score": 100.0,
            "checks": [
                {
                    "name": "database",
                    "category": "provider",
                    "passed": True,
                    "severity": "LOW",
                    "message": "Database is configured.",
                }
            ],
        },
        environment_registry_profile={
            "allowed": True,
            "active": True,
            "version": "prod-v1",
            "runtime_score": 100.0,
            "runtime_grade": "A",
            "configuration_fingerprint": "fingerprint-123",
            "environment": "production",
        },
        secret_governance_profile={
            "allowed": True,
            "score": 100.0,
            "credentials": [
                {
                    "name": "DATABASE_URL",
                    "provider": "environment",
                    "resolved": True,
                    "age_days": 10.0,
                    "days_until_expiry": 80.0,
                    "score": 100.0,
                    "grade": "A",
                    "allowed": True,
                    "recommendation": "USE",
                }
            ],
        },
    )

    report = ProductionReadinessReport()
    assert "Startup Readiness Gate" in report.readiness_summary_html(profile)
    assert "Startup Gate Controls" in report.readiness_checks_html(profile)
    assert "Environment Configuration Registry" in report.environment_registry_html(profile)
    assert "Credential Health and Rotation Governance" in report.secret_health_html(profile)

    with tempfile.TemporaryDirectory() as temp:
        path = report.generate(profile, Path(temp) / "readiness.html")
        html = path.read_text(encoding="utf-8")
        assert "Production Configuration and Runtime Safety" in html
        assert "prod-v1" in html
        assert "DATABASE_URL" in html
        assert "fingerprint-123" in html

    print("All production-readiness reporting assertions passed.")


if __name__ == "__main__":
    main()
