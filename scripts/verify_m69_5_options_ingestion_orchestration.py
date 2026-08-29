from __future__ import annotations

import inspect
import json
from pathlib import Path

import ingest_options_data
import ingestion_split_common


def main() -> None:
    parser = ingest_options_data.build_wrapper_parser()
    defaults = parser.parse_args([])
    source = inspect.getsource(
        ingestion_split_common.advance_institutional_options_workflow
    )
    finalize_source = inspect.getsource(ingestion_split_common.finalize_shared_state)

    checks = {
        "valuation_enabled_by_default": defaults.skip_option_valuation is False,
        "require_gate_available": hasattr(defaults, "require_option_valuation"),
        "limit_control_available": hasattr(defaults, "option_valuation_limit"),
        "contracts_before_valuation": source.index('"contracts",\n        run_contracts')
        < source.index("if run_option_valuation:"),
        "valuation_before_decisions": source.index("if run_option_valuation:")
        < source.index('"decisions",\n        run_decisions'),
        "single_build_handoff": (
            'get("stages", {}).get("option_valuation")' in finalize_source
            and "refresh_option_valuation_intelligence(" not in finalize_source
        ),
    }

    report_path = Path("reports/market_ingestion/options_finalization_latest.json")
    runtime = {"report_available": report_path.exists()}
    if report_path.exists():
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        valuation = payload.get("option_valuation_intelligence") or {}
        runtime.update(
            {
                "status": valuation.get("status"),
                "built": valuation.get("built"),
                "valuation_run_id": valuation.get("valuation_run_id"),
            }
        )

    for name, passed in checks.items():
        print(f"{name}: {'PASS' if passed else 'FAIL'}")
    print("runtime_report:", json.dumps(runtime, sort_keys=True))

    if not all(checks.values()):
        raise SystemExit("Milestone 69.5 options-ingestion orchestration acceptance FAILED")
    print("Milestone 69.5 options-ingestion orchestration acceptance PASSED")


if __name__ == "__main__":
    main()
