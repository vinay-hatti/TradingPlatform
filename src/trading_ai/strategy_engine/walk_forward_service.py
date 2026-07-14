from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from .walk_forward_engine import Evaluator, InstitutionalWalkForwardEngine
from .walk_forward_policy import WalkForwardPolicy
from .walk_forward_profile import WalkForwardProfile


class InstitutionalWalkForwardService:
    def __init__(
        self,
        policy: WalkForwardPolicy | None = None,
        engine: InstitutionalWalkForwardEngine | None = None,
    ) -> None:
        self.policy = policy or WalkForwardPolicy()
        self.engine = engine or InstitutionalWalkForwardEngine(self.policy)

    def validate(
        self,
        observations: Sequence[Any],
        parameter_grid: Iterable[dict[str, Any]],
        evaluator: Evaluator,
    ) -> WalkForwardProfile:
        return self.engine.run(observations, parameter_grid, evaluator)
