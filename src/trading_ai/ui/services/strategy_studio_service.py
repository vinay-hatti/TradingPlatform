from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from trading_ai.ui.models.strategy_studio import (
    AuditEvent,
    ExperimentRecord,
    ExperimentRequest,
    PromotionRequest,
    ShadowDeploymentRecord,
    ShadowDeploymentRequest,
    StrategyDraftRequest,
    StrategyParameter,
    StrategyVersionRecord,
)


class StrategyStudioService:
    def __init__(
        self,
        state_path: str | Path = "reports/ui/strategy_studio_state.json",
        audit_path: str | Path = "reports/audit/strategy_studio_events.jsonl",
    ) -> None:
        self.state_path = Path(state_path)
        self.audit_path = Path(audit_path)
        self._lock = RLock()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    def _load(self):
        if not self.state_path.exists():
            return {
                "versions": [],
                "deployments": [],
                "experiments": [],
                "promotions": {},
            }
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _save(self, state):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix(".tmp")
        temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temp.replace(self.state_path)

    def _audit(self, event_type, actor, object_type, object_id, details):
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        event = AuditEvent(
            timestamp=self._now(),
            event_type=event_type,
            actor_user_id=actor.user_id,
            object_type=object_type,
            object_id=object_id,
            details=details,
        )
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json() + "\n")

    @staticmethod
    def _checksum(parameters: list[StrategyParameter]) -> str:
        payload = json.dumps(
            [p.model_dump(mode="json") for p in parameters],
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_parameter(parameter: StrategyParameter) -> list[str]:
        errors = []
        value = parameter.value
        if parameter.value_type == "int" and not isinstance(value, int):
            errors.append(f"{parameter.name} must be int.")
        elif parameter.value_type == "float" and not isinstance(value, (int, float)):
            errors.append(f"{parameter.name} must be float.")
        elif parameter.value_type == "bool" and not isinstance(value, bool):
            errors.append(f"{parameter.name} must be bool.")
        elif parameter.value_type == "str" and not isinstance(value, str):
            errors.append(f"{parameter.name} must be str.")
        if isinstance(value, (int, float)):
            if parameter.minimum is not None and value < parameter.minimum:
                errors.append(f"{parameter.name} is below minimum {parameter.minimum}.")
            if parameter.maximum is not None and value > parameter.maximum:
                errors.append(f"{parameter.name} exceeds maximum {parameter.maximum}.")
        return errors

    def create_version(self, request: StrategyDraftRequest) -> StrategyVersionRecord:
        with self._lock:
            state = self._load()
            existing = [
                StrategyVersionRecord.model_validate(v)
                for v in state["versions"]
                if v["strategy_id"] == request.strategy_id
            ]
            errors = []
            for parameter in request.parameters:
                errors.extend(self._validate_parameter(parameter))
            version = StrategyVersionRecord(
                version_id=f"sv-{uuid4().hex[:16]}",
                strategy_id=request.strategy_id,
                version_number=max([v.version_number for v in existing], default=0) + 1,
                created_at=self._now(),
                created_by=request.actor.user_id,
                display_name=request.display_name,
                description=request.description,
                parameters=request.parameters,
                tags=request.tags,
                checksum=self._checksum(request.parameters),
                status="VALIDATED" if not errors else "DRAFT",
                validation_errors=errors,
            )
            state["versions"].append(version.model_dump(mode="json"))
            self._save(state)
            self._audit(
                "STRATEGY_VERSION_CREATED",
                request.actor,
                "strategy_version",
                version.version_id,
                {"strategy_id": version.strategy_id, "checksum": version.checksum},
            )
            return version

    def list_versions(self, strategy_id: str | None = None):
        versions = [StrategyVersionRecord.model_validate(v) for v in self._load()["versions"]]
        if strategy_id:
            versions = [v for v in versions if v.strategy_id == strategy_id]
        return sorted(versions, key=lambda v: (v.strategy_id, v.version_number), reverse=True)

    def get_version(self, version_id: str):
        value = next((v for v in self.list_versions() if v.version_id == version_id), None)
        if value is None:
            raise KeyError(version_id)
        return value

    def create_shadow(self, request: ShadowDeploymentRequest):
        if "strategy.shadow.deploy" not in request.actor.permissions:
            raise PermissionError("Missing strategy.shadow.deploy permission.")
        version = self.get_version(request.version_id)
        if version.status != "VALIDATED":
            raise ValueError("Only validated strategy versions may enter shadow deployment.")
        if version.strategy_id != request.strategy_id:
            raise ValueError("Version does not belong to requested strategy.")
        with self._lock:
            state = self._load()
            deployment = ShadowDeploymentRecord(
                deployment_id=f"shadow-{uuid4().hex[:16]}",
                strategy_id=request.strategy_id,
                version_id=request.version_id,
                created_at=self._now(),
                created_by=request.actor.user_id,
                symbols=[s.upper() for s in request.symbols],
                allocation_pct=request.allocation_pct,
                start_reason=request.start_reason,
            )
            state["deployments"].append(deployment.model_dump(mode="json"))
            self._save(state)
            self._audit("SHADOW_DEPLOYMENT_CREATED", request.actor, "shadow_deployment",
                        deployment.deployment_id, deployment.model_dump(mode="json"))
            return deployment

    def list_deployments(self):
        return [ShadowDeploymentRecord.model_validate(v) for v in self._load()["deployments"]]

    def create_experiment(self, request: ExperimentRequest):
        if "strategy.experiment.create" not in request.actor.permissions:
            raise PermissionError("Missing strategy.experiment.create permission.")
        for variant in request.variants:
            version = self.get_version(variant.version_id)
            if version.strategy_id != request.strategy_id:
                raise ValueError(f"Variant {variant.label} does not belong to strategy.")
            if version.status != "VALIDATED":
                raise ValueError(f"Variant {variant.label} is not validated.")
        with self._lock:
            state = self._load()
            record = ExperimentRecord(
                experiment_id=f"exp-{uuid4().hex[:16]}",
                experiment_name=request.experiment_name,
                strategy_id=request.strategy_id,
                created_at=self._now(),
                created_by=request.actor.user_id,
                variants=request.variants,
                metric=request.metric,
                minimum_observations=request.minimum_observations,
                status="RUNNING",
                observations={v.label: 0 for v in request.variants},
                scores={v.label: 0.0 for v in request.variants},
            )
            state["experiments"].append(record.model_dump(mode="json"))
            self._save(state)
            self._audit("EXPERIMENT_CREATED", request.actor, "experiment",
                        record.experiment_id, record.model_dump(mode="json"))
            return record

    def list_experiments(self):
        return [ExperimentRecord.model_validate(v) for v in self._load()["experiments"]]

    def promote(self, experiment_id: str, request: PromotionRequest):
        if "strategy.promote" not in request.actor.permissions:
            raise PermissionError("Missing strategy.promote permission.")
        if not request.confirmation_token.startswith("CONFIRM-STRATEGY-"):
            raise PermissionError("Invalid strategy promotion confirmation token.")
        with self._lock:
            state = self._load()
            record = next(
                (ExperimentRecord.model_validate(v) for v in state["experiments"]
                 if v["experiment_id"] == experiment_id),
                None,
            )
            if record is None:
                raise KeyError(experiment_id)
            if request.version_id not in {v.version_id for v in record.variants}:
                raise ValueError("Promotion version must be an experiment variant.")
            label = next(v.label for v in record.variants if v.version_id == request.version_id)
            if record.observations.get(label, 0) < record.minimum_observations:
                raise ValueError("Minimum observations not reached for selected variant.")
            record.status = "PROMOTED"
            record.promoted_version_id = request.version_id
            for index, item in enumerate(state["experiments"]):
                if item["experiment_id"] == experiment_id:
                    state["experiments"][index] = record.model_dump(mode="json")
                    break
            state["promotions"][record.strategy_id] = {
                "version_id": request.version_id,
                "promoted_at": self._now().isoformat(),
                "promoted_by": request.actor.user_id,
                "reason": request.reason,
                "mode": "PAPER_OR_SHADOW_ONLY",
            }
            self._save(state)
            self._audit("STRATEGY_VERSION_PROMOTED", request.actor, "experiment",
                        experiment_id, {"version_id": request.version_id, "reason": request.reason})
            return record
