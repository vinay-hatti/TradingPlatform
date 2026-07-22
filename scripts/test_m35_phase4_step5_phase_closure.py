import json
import tempfile
from datetime import date
from pathlib import Path

from trading_ai.scanner.option_surface_phase_closure.service import (
    OptionSurfacePhaseClosureService,
)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)

        step1 = root / (
            "reports/m35/phase4/"
            "historical_options_feature_store"
        )
        write_json(step1 / "run.json", {"features_generated": 100})
        touch(step1 / "features.jsonl")

        step2 = root / (
            "reports/m35/phase4/option_surface_analytics"
        )
        write_json(step2 / "run.json", {"symbols_evaluated": 10})
        touch(step2 / "expiration_surfaces.jsonl")
        touch(step2 / "symbol_surface_profiles.jsonl")

        step3 = root / (
            "reports/m35/phase4/option_surface_persistence"
        )
        write_json(step3 / "run.json", {"symbol_records_persisted": 10})
        touch(step3 / "expiration_surfaces.csv")
        touch(step3 / "symbol_surface_profiles.csv")
        write_json(step3 / "governance_summary.json", {})

        step4 = root / (
            "reports/m35/phase4/"
            "option_surface_decision_integration"
        )
        write_json(step4 / "run.json", {"eligible_count": 8})
        touch(step4 / "surface_decision_features.jsonl")

        profile = OptionSurfacePhaseClosureService().run(
            as_of_date=date(2026, 7, 20),
            project_root=root,
            execute_pipeline=False,
            include_review=False,
        )

        assert profile.phase_status == "COMPLETE"
        assert not profile.missing_artifacts
        assert len(profile.existing_artifacts) == 11
        assert "step1" in profile.consolidated_metrics
        assert "step4" in profile.consolidated_metrics

    print("Milestone 35 Phase 4 Step 5 closure assertions passed.")


if __name__ == "__main__":
    main()
