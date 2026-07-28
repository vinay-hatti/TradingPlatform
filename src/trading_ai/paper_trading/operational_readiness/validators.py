from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from .profile import ReadinessControl
from .status_registry import PhaseStatusRegistry


def _status(score: float) -> str:
    if score >= 90:
        return "PASS"
    if score >= 70:
        return "WARN"
    return "FAIL"


def _parse_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


class EnvironmentValidator:
    DATABASE_KEYS = (
        "DATABASE_URL",
        "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME",
    )
    POLYGON_KEYS = (
        "POLYGON_API_KEY", "POLYGON_KEY", "POLYGON_TOKEN",
    )

    def _configuration_sources(self, root: Path) -> tuple[dict[str, str], tuple[str, ...]]:
        combined = dict(os.environ)
        evidence: list[str] = []

        for candidate in (root / ".env", root / ".env.local", root / "config/.env"):
            parsed = _parse_dotenv(candidate)
            if parsed:
                combined.update({k: v for k, v in parsed.items() if v})
                evidence.append(str(candidate))

        return combined, tuple(evidence)

    def validate(
        self,
        *,
        repo_root: str | Path,
        require_database_url: bool = False,
        require_polygon_key: bool = False,
        broker_mode: str = "PAPER",
    ) -> tuple[ReadinessControl, ...]:
        root = Path(repo_root)
        controls: list[ReadinessControl] = []

        required_paths = (
            root / "pyproject.toml",
            root / "src/trading_ai",
            root / "scripts",
            root / "reports",
        )
        existing = [str(path) for path in required_paths if path.exists()]
        missing = [str(path) for path in required_paths if not path.exists()]
        score = 100.0 if not missing else max(0.0, 100 - 25 * len(missing))
        controls.append(
            ReadinessControl(
                control_id="ENV-REPOSITORY-STRUCTURE",
                category="ENVIRONMENT",
                title="Repository structure",
                status=_status(score),
                score=score,
                weight=1.0,
                evidence=tuple(existing),
                errors=tuple(f"MISSING_PATH:{path}" for path in missing),
                recommendation="Restore required project paths." if missing else "",
            )
        )

        config, config_sources = self._configuration_sources(root)

        database_present = bool(config.get("DATABASE_URL")) or all(
            config.get(name)
            for name in ("DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME")
        )
        db_score = 100.0 if database_present else (40.0 if require_database_url else 80.0)
        controls.append(
            ReadinessControl(
                control_id="ENV-DATABASE-CONFIGURATION",
                category="DATA",
                title="Database configuration",
                status=_status(db_score),
                score=db_score,
                weight=1.0,
                evidence=(
                    ("DATABASE_CONFIGURATION_PRESENT",) + config_sources
                    if database_present else config_sources
                ),
                warnings=() if database_present else ("DATABASE_CONFIGURATION_NOT_DETECTED",),
                errors=("DATABASE_CONFIGURATION_REQUIRED",) if require_database_url and not database_present else (),
                recommendation="Configure DATABASE_URL or DB_* variables in shell or .env." if not database_present else "",
                metadata={"configuration_sources": list(config_sources)},
            )
        )

        polygon_present = any(bool(config.get(name)) for name in self.POLYGON_KEYS)
        polygon_score = 100.0 if polygon_present else (40.0 if require_polygon_key else 80.0)
        controls.append(
            ReadinessControl(
                control_id="ENV-POLYGON-CONFIGURATION",
                category="DATA",
                title="Polygon configuration",
                status=_status(polygon_score),
                score=polygon_score,
                weight=1.0,
                evidence=(
                    ("POLYGON_CONFIGURATION_PRESENT",) + config_sources
                    if polygon_present else config_sources
                ),
                warnings=() if polygon_present else ("POLYGON_CONFIGURATION_NOT_DETECTED",),
                errors=("POLYGON_CONFIGURATION_REQUIRED",) if require_polygon_key and not polygon_present else (),
                recommendation="Configure Polygon credentials in shell or .env." if not polygon_present else "",
                metadata={"configuration_sources": list(config_sources)},
            )
        )

        paper = broker_mode.upper() == "PAPER"
        controls.append(
            ReadinessControl(
                control_id="ENV-BROKER-MODE",
                category="BROKER",
                title="Paper broker mode",
                status="PASS" if paper else "FAIL",
                score=100.0 if paper else 0.0,
                weight=2.0,
                evidence=(f"BROKER_MODE={broker_mode.upper()}",),
                errors=() if paper else ("BROKER_NOT_IN_PAPER_MODE",),
                recommendation="Switch broker routing to PAPER." if not paper else "",
            )
        )
        return tuple(controls)


class DependencyValidator:
    def __init__(self, registry: PhaseStatusRegistry | None = None) -> None:
        self.registry = registry or PhaseStatusRegistry()

    def validate(
        self,
        phase_reports: Mapping[int, Mapping[str, Any]],
        required_phases: tuple[int, ...],
    ) -> tuple[ReadinessControl, ...]:
        controls: list[ReadinessControl] = []
        for phase in required_phases:
            report = phase_reports.get(phase)
            if not report:
                controls.append(
                    ReadinessControl(
                        control_id=f"DEP-PHASE-{phase}",
                        category="INTEGRATION",
                        title=f"Phase {phase} report",
                        status="FAIL",
                        score=0.0,
                        weight=1.0,
                        errors=("MISSING_PHASE_REPORT",),
                        recommendation=f"Generate the Milestone 51 Phase {phase} report.",
                    )
                )
                continue

            status = str(
                report.get("overall_status")
                or report.get("status")
                or "UNKNOWN"
            )
            disposition = self.registry.classify(phase, status)
            if disposition.disposition == "PASS":
                control_status, score = "PASS", 100.0
                warnings, errors = (), ()
                recommendation = ""
            elif disposition.disposition == "WARN":
                control_status, score = "WARN", 75.0
                warnings = (f"PHASE_STATUS_REVIEW:{status}",)
                errors = ()
                recommendation = (
                    f"Review Phase {phase} controlled state; it does not by itself "
                    "block paper-trading milestone acceptance."
                )
            else:
                control_status, score = "FAIL", 20.0
                warnings = ()
                errors = (f"UNACCEPTED_PHASE_STATUS:{status}",)
                recommendation = f"Resolve Phase {phase} failure before sign-off."

            controls.append(
                ReadinessControl(
                    control_id=f"DEP-PHASE-{phase}",
                    category="INTEGRATION",
                    title=f"Phase {phase} report",
                    status=control_status,
                    score=score,
                    weight=1.0,
                    evidence=(status, disposition.reason),
                    warnings=warnings,
                    errors=errors,
                    recommendation=recommendation,
                    metadata={"disposition": disposition.disposition},
                )
            )
        return tuple(controls)


class GovernanceValidator:
    def validate(
        self,
        phase_reports: Mapping[int, Mapping[str, Any]],
    ) -> tuple[ReadinessControl, ...]:
        p5 = phase_reports.get(5, {})
        p6 = phase_reports.get(6, {})
        p8 = phase_reports.get(8, {})
        metadata5 = p5.get("metadata") or {}
        decision5 = p5.get("decision") or p5.get("authorization") or {}
        metadata6 = p6.get("metadata") or {}
        authorization8 = p8.get("authorization") or {}

        checks = [
            (
                "GOV-PAPER-ONLY",
                "Paper-only enforcement",
                not bool(metadata5.get("live_trading_enabled", False))
                and not bool(metadata6.get("live_trading_enabled", False)),
                "FAIL",
                "Live trading must remain disabled.",
            ),
            (
                "GOV-KILL-SWITCH",
                "Kill-switch control",
                "kill_switch_active" in decision5
                or "kill_switch_active" in authorization8
                or bool(metadata5.get("paper_only", True)),
                "FAIL",
                "Expose and validate kill-switch state.",
            ),
            (
                "GOV-DUPLICATE-RUN",
                "Duplicate-run prevention",
                bool(metadata6.get("duplicate_run_prevention", False)),
                "FAIL",
                "Enable Phase 6 duplicate-run prevention.",
            ),
            (
                "GOV-RESTART-SAFE",
                "Restart-safe scheduler state",
                bool(metadata6.get("restart_safe", False)),
                "FAIL",
                "Enable restart-safe Phase 6 state persistence.",
            ),
        ]

        controls = [
            ReadinessControl(
                control_id=control_id,
                category="GOVERNANCE",
                title=title,
                status="PASS" if passed else failure_status,
                score=100.0 if passed else 0.0,
                weight=1.5,
                evidence=("CONTROL_PRESENT",) if passed else (),
                errors=() if passed else ("CONTROL_NOT_SATISFIED",),
                recommendation="" if passed else recommendation,
            )
            for control_id, title, passed, failure_status, recommendation in checks
        ]

        recovery_status = str(p8.get("status") or p8.get("overall_status") or "UNKNOWN")
        recovery_blocked = "BLOCKED" in recovery_status.upper()
        recovery_failed = any(
            token in recovery_status.upper()
            for token in ("FAILED", "ERROR", "CORRUPT", "UNSAFE")
        )
        if recovery_failed:
            controls.append(
                ReadinessControl(
                    control_id="GOV-RECOVERY",
                    category="GOVERNANCE",
                    title="Recovery governance",
                    status="FAIL",
                    score=0.0,
                    weight=1.5,
                    evidence=(recovery_status,),
                    errors=("RECOVERY_GOVERNANCE_FAILED",),
                    recommendation="Resolve Phase 8 recovery failure.",
                )
            )
        elif recovery_blocked:
            controls.append(
                ReadinessControl(
                    control_id="GOV-RECOVERY",
                    category="GOVERNANCE",
                    title="Recovery governance",
                    status="WARN",
                    score=75.0,
                    weight=1.5,
                    evidence=(recovery_status, "CONTROLLED_RECOVERY_BLOCK"),
                    warnings=("RECOVERY_CURRENTLY_BLOCKED",),
                    recommendation=(
                        "Review the recovery block. A controlled block does not "
                        "automatically fail paper-trading acceptance."
                    ),
                )
            )
        else:
            controls.append(
                ReadinessControl(
                    control_id="GOV-RECOVERY",
                    category="GOVERNANCE",
                    title="Recovery governance",
                    status="PASS",
                    score=100.0,
                    weight=1.5,
                    evidence=(recovery_status,),
                )
            )

        return tuple(controls)
