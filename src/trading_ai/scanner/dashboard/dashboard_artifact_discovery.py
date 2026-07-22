from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DiscoveredArtifact:
    stage_name: str
    path: Path | None
    payload: dict[str, Any] | None
    candidates: tuple[str, ...] = ()


class DashboardArtifactDiscoveryService:
    """
    Discovers the newest usable Milestone 35 Phase 5 dashboard artifact
    for each workflow stage.

    Discovery is intentionally conservative:
    - only JSON objects are accepted
    - known registries are excluded
    - malformed artifacts are ignored
    - explicit paths always override discovery
    """

    STAGE_PATTERNS: dict[str, tuple[str, ...]] = {
        "MARKET_SCAN": (
            "reports/m35/phase5/dashboard/**/*market*scan*.json",
            "reports/m35/phase5/dashboard/**/*ranked*opportunit*.json",
            "reports/m35/phase5/**/*market*scan*.json",
        ),
        "CANDIDATE_INSPECTION": (
            "reports/m35/phase5/dashboard/**/*candidate*inspection*.json",
            "reports/m35/phase5/dashboard/**/*candidate*detail*.json",
            "reports/m35/phase5/**/*candidate*inspection*.json",
        ),
        "OPTION_CHAIN": (
            "reports/m35/phase5/dashboard/**/*option*chain*.json",
            "reports/m35/phase5/**/*option*chain*.json",
        ),
        "STRATEGY_COMPARISON": (
            "reports/m35/phase5/dashboard/strategy_comparison/*.json",
            "reports/m35/phase5/dashboard/**/*strategy*comparison*.json",
        ),
        "INSTITUTIONAL_DECISION": (
            "reports/m35/phase5/dashboard/institutional_decision/*.json",
            "reports/m35/phase5/dashboard/**/*institutional*decision*.json",
        ),
        "PAPER_TRADE_PREPARATION": (
            "reports/m35/phase5/dashboard/paper_trade_preparation/*.json",
            "reports/m35/phase5/dashboard/**/*paper*trade*preparation*.json",
        ),
        "PAPER_TRADE_LIFECYCLE": (
            "reports/m35/phase5/dashboard/paper_trade/*_lifecycle.json",
            "reports/m35/phase5/dashboard/**/*lifecycle*.json",
        ),
        "PERFORMANCE": (
            "reports/m35/phase5/dashboard/performance/paper_trade_performance.json",
            "reports/m35/phase5/dashboard/performance/*.json",
        ),
    }

    EXCLUDED_NAMES = {
        "paper_order_registry.json",
        "dashboard_workflow_report.json",
        "dashboard_artifact_discovery.json",
    }

    def discover(
        self,
        project_root: Path,
        explicit_paths: dict[str, Path | None] | None = None,
    ) -> dict[str, DiscoveredArtifact]:
        explicit_paths = explicit_paths or {}
        results: dict[str, DiscoveredArtifact] = {}

        for stage_name, patterns in self.STAGE_PATTERNS.items():
            explicit = explicit_paths.get(stage_name)
            if explicit is not None:
                resolved = self._resolve(project_root, explicit)
                payload = self._load_json_object(resolved)
                results[stage_name] = DiscoveredArtifact(
                    stage_name=stage_name,
                    path=resolved if payload is not None else None,
                    payload=payload,
                    candidates=(str(resolved),),
                )
                continue

            candidates = self._candidate_paths(project_root, patterns)
            selected_path: Path | None = None
            selected_payload: dict[str, Any] | None = None

            for candidate in candidates:
                payload = self._load_json_object(candidate)
                if payload is None:
                    continue
                if not self._looks_like_stage(stage_name, payload):
                    continue
                selected_path = candidate
                selected_payload = payload
                break

            results[stage_name] = DiscoveredArtifact(
                stage_name=stage_name,
                path=selected_path,
                payload=selected_payload,
                candidates=tuple(str(path) for path in candidates),
            )

        return results

    def _candidate_paths(
        self,
        project_root: Path,
        patterns: tuple[str, ...],
    ) -> list[Path]:
        discovered: dict[str, Path] = {}

        for pattern in patterns:
            for path in project_root.glob(pattern):
                if not path.is_file():
                    continue
                if path.name in self.EXCLUDED_NAMES:
                    continue
                discovered[str(path.resolve())] = path.resolve()

        return sorted(
            discovered.values(),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    def _looks_like_stage(
        self,
        stage_name: str,
        payload: dict[str, Any],
    ) -> bool:
        if stage_name == "MARKET_SCAN":
            return any(
                key in payload
                for key in (
                    "ranked_opportunities",
                    "opportunities",
                    "scan_results",
                    "candidates",
                    "symbol",
                )
            )

        if stage_name == "CANDIDATE_INSPECTION":
            return any(
                key in payload
                for key in (
                    "candidate",
                    "inspection",
                    "symbol",
                    "direction",
                )
            )

        if stage_name == "OPTION_CHAIN":
            return any(
                key in payload
                for key in (
                    "contracts",
                    "option_chain",
                    "calls",
                    "puts",
                    "symbol",
                )
            )

        if stage_name == "STRATEGY_COMPARISON":
            return any(
                key in payload
                for key in (
                    "ranked_strategies",
                    "generated_strategies",
                    "strategies",
                )
            )

        if stage_name == "INSTITUTIONAL_DECISION":
            return (
                "decision" in payload
                and (
                    "selected_strategy_id" in payload
                    or "approved_candidates" in payload
                    or "rejected_candidates" in payload
                )
            )

        if stage_name == "PAPER_TRADE_PREPARATION":
            return (
                "paper_trade_ready" in payload
                and (
                    "refreshed_debit" in payload
                    or "paper_trade_payload" in payload
                )
            )

        if stage_name == "PAPER_TRADE_LIFECYCLE":
            return isinstance(payload.get("order"), dict)

        if stage_name == "PERFORMANCE":
            return isinstance(payload.get("summary"), dict)

        return False

    def _resolve(
        self,
        project_root: Path,
        path: Path,
    ) -> Path:
        return path if path.is_absolute() else project_root / path

    def _load_json_object(
        self,
        path: Path,
    ) -> dict[str, Any] | None:
        if not path.exists() or not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None
