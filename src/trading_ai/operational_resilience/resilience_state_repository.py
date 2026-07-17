from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path

from .resilience_profile import BulkheadState, CircuitBreakerState

class JsonResilienceStateRepository:
    def __init__(
        self,
        path: str | Path = (
            "data/operational_resilience/resilience_state.json"
        ),
    ) -> None:
        self.path = Path(path)

    def _load(self) -> tuple[
        dict[str, CircuitBreakerState],
        dict[str, BulkheadState],
    ]:
        if not self.path.exists():
            return {}, {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        circuits = {
            key: CircuitBreakerState(**value)
            for key, value in payload.get("circuits", {}).items()
        }
        bulkheads = {
            key: BulkheadState(**value)
            for key, value in payload.get("bulkheads", {}).items()
        }
        return circuits, bulkheads

    def _save(
        self,
        circuits: dict[str, CircuitBreakerState],
        bulkheads: dict[str, BulkheadState],
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps(
                {
                    "circuits": {
                        key: asdict(value) for key, value in circuits.items()
                    },
                    "bulkheads": {
                        key: asdict(value) for key, value in bulkheads.items()
                    },
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        temp.replace(self.path)

    def circuit(self, dependency_name: str) -> CircuitBreakerState:
        circuits, _ = self._load()
        return circuits.get(
            dependency_name,
            CircuitBreakerState(
                circuit_id=f"circuit:{dependency_name}",
                dependency_name=dependency_name,
            ),
        )

    def bulkhead(self, dependency_name: str) -> BulkheadState:
        _, bulkheads = self._load()
        return bulkheads.get(
            dependency_name,
            BulkheadState(
                bulkhead_id=f"bulkhead:{dependency_name}",
                dependency_name=dependency_name,
            ),
        )

    def save_circuit(
        self,
        state: CircuitBreakerState,
    ) -> CircuitBreakerState:
        circuits, bulkheads = self._load()
        circuits[state.dependency_name] = state
        self._save(circuits, bulkheads)
        return state

    def save_bulkhead(
        self,
        state: BulkheadState,
    ) -> BulkheadState:
        circuits, bulkheads = self._load()
        bulkheads[state.dependency_name] = state
        self._save(circuits, bulkheads)
        return state
