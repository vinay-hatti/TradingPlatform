import json
from pathlib import Path

from trading_ai.strategy_engine.decision_serialization import (
    decision_run_to_dict,
)
from trading_ai.strategy_engine.institutional_decision_engine import (
    InstitutionalDecisionEngine,
)


class InstitutionalDecisionService:
    """
    Unified application-facing Phase 12 service.
    """

    def __init__(
        self,
        engine: InstitutionalDecisionEngine | None = None,
    ):
        self.engine = (
            engine
            or InstitutionalDecisionEngine()
        )

    def run(
        self,
        request,
    ):
        return self.engine.run(
            request
        )

    def run_and_export(
        self,
        request,
        output_file,
    ):
        result = self.run(
            request
        )

        path = Path(
            output_file
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            json.dumps(
                decision_run_to_dict(
                    result
                ),
                indent=2,
                sort_keys=True,
            )
        )

        return result, path
