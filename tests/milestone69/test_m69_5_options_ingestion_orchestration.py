from __future__ import annotations

import inspect
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import ingest_options_data
import ingestion_split_common


def test_options_ingestion_exposes_governed_m69_controls():
    parser = ingest_options_data.build_wrapper_parser()
    args = parser.parse_args([])
    assert args.skip_option_valuation is False
    assert args.require_option_valuation is False
    assert args.option_valuation_limit is None

    configured = parser.parse_args(
        [
            "--skip-option-valuation",
            "--require-option-valuation",
            "--option-valuation-limit",
            "125",
        ]
    )
    assert configured.skip_option_valuation is True
    assert configured.require_option_valuation is True
    assert configured.option_valuation_limit == 125


def test_m69_runs_after_contract_optimization_and_before_decisions():
    source = inspect.getsource(
        ingestion_split_common.advance_institutional_options_workflow
    )
    contract_stage = source.index('"contracts",\n        run_contracts')
    valuation_stage = source.index("if run_option_valuation:")
    decision_stage = source.index('"decisions",\n        run_decisions')
    assert contract_stage < valuation_stage < decision_stage


def test_finalization_reuses_embedded_valuation_without_duplicate_build():
    source = inspect.getsource(ingestion_split_common.finalize_shared_state)
    assert 'get("stages", {}).get("option_valuation")' in source
    assert "refresh_option_valuation_intelligence(" not in source
