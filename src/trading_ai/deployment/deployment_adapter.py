from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class DeploymentTargetState:
    environment: str
    active_slot: str
    candidate_slot: str | None
    traffic_percent: int
    active_version: str | None
    candidate_version: str | None

class DeploymentAdapter(Protocol):
    def current_state(self, environment: str) -> DeploymentTargetState: ...
    def deploy_to_slot(self, *, environment: str, slot: str, artifact_location: str, version: str) -> None: ...
    def set_traffic(self, *, environment: str, slot: str, percent: int) -> None: ...
    def promote_slot(self, *, environment: str, slot: str) -> None: ...
    def remove_slot(self, *, environment: str, slot: str) -> None: ...
    def restart(self, *, environment: str, slot: str) -> None: ...

class InMemoryDeploymentAdapter:
    def __init__(self) -> None:
        self._states: dict[str, DeploymentTargetState] = {}

    def seed(self, state: DeploymentTargetState) -> None:
        self._states[state.environment.upper()] = state

    def current_state(self, environment: str) -> DeploymentTargetState:
        key = environment.upper()
        if key not in self._states:
            self._states[key] = DeploymentTargetState(
                environment=key, active_slot="blue", candidate_slot=None,
                traffic_percent=100, active_version=None, candidate_version=None
            )
        return self._states[key]

    def deploy_to_slot(self, *, environment: str, slot: str, artifact_location: str, version: str) -> None:
        state = self.current_state(environment)
        self._states[environment.upper()] = DeploymentTargetState(
            environment=state.environment, active_slot=state.active_slot,
            candidate_slot=slot, traffic_percent=0,
            active_version=state.active_version, candidate_version=version
        )

    def set_traffic(self, *, environment: str, slot: str, percent: int) -> None:
        state = self.current_state(environment)
        self._states[environment.upper()] = DeploymentTargetState(
            environment=state.environment, active_slot=state.active_slot,
            candidate_slot=slot, traffic_percent=percent,
            active_version=state.active_version,
            candidate_version=state.candidate_version
        )

    def promote_slot(self, *, environment: str, slot: str) -> None:
        state = self.current_state(environment)
        version = state.candidate_version if state.candidate_slot == slot else state.active_version
        self._states[environment.upper()] = DeploymentTargetState(
            environment=state.environment, active_slot=slot,
            candidate_slot=None, traffic_percent=100,
            active_version=version, candidate_version=None
        )

    def remove_slot(self, *, environment: str, slot: str) -> None:
        state = self.current_state(environment)
        if state.candidate_slot == slot:
            self._states[environment.upper()] = DeploymentTargetState(
                environment=state.environment, active_slot=state.active_slot,
                candidate_slot=None, traffic_percent=100,
                active_version=state.active_version, candidate_version=None
            )

    def restart(self, *, environment: str, slot: str) -> None:
        self.current_state(environment)
