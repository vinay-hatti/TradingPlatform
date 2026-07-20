from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from trading_ai.ui.models.paper_commands import GovernedActor


class StrategyParameter(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    value: Any
    value_type: Literal["int", "float", "bool", "str"]
    minimum: float | None = None
    maximum: float | None = None
    description: str = ""


class StrategyDraftRequest(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    base_version_id: str | None = None
    parameters: list[StrategyParameter] = Field(min_length=1, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=30)
    actor: GovernedActor

    @model_validator(mode="after")
    def unique_names(self):
        names = [p.name for p in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("Strategy parameter names must be unique.")
        return self


class StrategyVersionRecord(BaseModel):
    version_id: str
    strategy_id: str
    version_number: int
    created_at: datetime
    created_by: str
    display_name: str
    description: str
    parameters: list[StrategyParameter]
    tags: list[str]
    checksum: str
    status: Literal["DRAFT", "VALIDATED", "ARCHIVED"] = "DRAFT"
    validation_errors: list[str] = Field(default_factory=list)


class ShadowDeploymentRequest(BaseModel):
    strategy_id: str
    version_id: str
    symbols: list[str] = Field(min_length=1, max_length=100)
    allocation_pct: float = Field(default=0.0, ge=0, le=0.10)
    start_reason: str = Field(min_length=5, max_length=500)
    actor: GovernedActor


class ShadowDeploymentRecord(BaseModel):
    deployment_id: str
    strategy_id: str
    version_id: str
    created_at: datetime
    created_by: str
    symbols: list[str]
    allocation_pct: float
    status: Literal["SHADOW", "STOPPED"] = "SHADOW"
    start_reason: str
    stop_reason: str | None = None


class ExperimentVariant(BaseModel):
    label: str = Field(min_length=1, max_length=20)
    version_id: str
    traffic_pct: float = Field(gt=0, le=100)


class ExperimentRequest(BaseModel):
    experiment_name: str = Field(min_length=1, max_length=160)
    strategy_id: str
    variants: list[ExperimentVariant] = Field(min_length=2, max_length=5)
    metric: Literal["NET_PNL", "WIN_RATE", "SHARPE", "DRAWDOWN"] = "NET_PNL"
    minimum_observations: int = Field(default=30, ge=10, le=100000)
    actor: GovernedActor

    @model_validator(mode="after")
    def traffic_totals(self):
        total = sum(v.traffic_pct for v in self.variants)
        if abs(total - 100.0) > 0.001:
            raise ValueError("Experiment traffic percentages must total 100.")
        return self


class ExperimentRecord(BaseModel):
    experiment_id: str
    experiment_name: str
    strategy_id: str
    created_at: datetime
    created_by: str
    variants: list[ExperimentVariant]
    metric: str
    minimum_observations: int
    status: Literal["DRAFT", "RUNNING", "STOPPED", "PROMOTED"] = "DRAFT"
    observations: dict[str, int] = Field(default_factory=dict)
    scores: dict[str, float] = Field(default_factory=dict)
    promoted_version_id: str | None = None


class PromotionRequest(BaseModel):
    version_id: str
    reason: str = Field(min_length=5, max_length=500)
    confirmation_token: str = Field(min_length=8, max_length=256)
    actor: GovernedActor


class AuditEvent(BaseModel):
    timestamp: datetime
    event_type: str
    actor_user_id: str
    object_type: str
    object_id: str
    details: dict
