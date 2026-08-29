from __future__ import annotations

import json
from pathlib import Path

BASELINE_OPTIONS_SECONDS = 1484.96
BASELINE_CONTRACT_SECONDS = 215.2351
BASELINE_VALUATION_SECONDS = 115.3198


def recursive_stage(node, key):
    if isinstance(node, dict):
        stages = node.get('stages')
        if isinstance(stages, dict) and key in stages and isinstance(stages[key], dict):
            return stages[key]
        for value in node.values():
            found = recursive_stage(value, key)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = recursive_stage(value, key)
            if found is not None:
                return found
    return None


def pct(before, after):
    return ((before - after) / before * 100.0) if before else 0.0


def main():
    root = Path(__file__).resolve().parents[1]
    finalization_path = root / 'reports/market_ingestion/options_finalization_latest.json'
    lifecycle_path = root / 'reports/market_ingestion/options_lifecycle_latest.json'
    if not finalization_path.exists() or not lifecycle_path.exists():
        raise RuntimeError('Run a full governed options cycle after M68.2.1.15.8.1 first.')

    finalization = json.loads(finalization_path.read_text())
    lifecycle = json.loads(lifecycle_path.read_text())
    contracts = recursive_stage(finalization, 'contracts') or {}
    valuation = recursive_stage(finalization, 'option_valuation') or {}
    current_options = lifecycle.get('elapsed_seconds')
    if current_options is None:
        raise RuntimeError('Latest lifecycle report has no elapsed_seconds; run options ingestion after M68.2.1.15.8.1 first.')

    current_contract = float(contracts.get('duration_seconds') or 0.0)
    current_valuation = float(valuation.get('duration_seconds') or 0.0)
    profile = valuation.get('parallel_profile') or {}

    print('=== M68.2.1.15.8.1 PERFORMANCE ===')
    print(f'phase1_options_seconds      : {BASELINE_OPTIONS_SECONDS:.2f}')
    print(f'current_options_seconds     : {float(current_options):.2f}')
    print(f'options_time_saved_seconds  : {BASELINE_OPTIONS_SECONDS-float(current_options):.2f}')
    print(f'options_reduction_pct       : {pct(BASELINE_OPTIONS_SECONDS,float(current_options)):.2f}%')
    print(f'options_speedup             : {BASELINE_OPTIONS_SECONDS/float(current_options):.3f}x')
    print()
    print('--- Contract optimization ---')
    print(f'phase1_contract_seconds     : {BASELINE_CONTRACT_SECONDS:.4f}')
    print(f'current_contract_seconds    : {current_contract:.4f}')
    print(f'contract_reduction_pct      : {pct(BASELINE_CONTRACT_SECONDS,current_contract):.2f}%')
    print(f'parallel_workers            : {contracts.get("parallel_workers", 1)}')
    print(f'execution_mode              : {contracts.get("execution_mode", "UNKNOWN")}')
    print()
    print('--- Option valuation ---')
    print(f'phase1_valuation_seconds    : {BASELINE_VALUATION_SECONDS:.4f}')
    print(f'current_valuation_seconds   : {current_valuation:.4f}')
    print(f'valuation_reduction_pct     : {pct(BASELINE_VALUATION_SECONDS,current_valuation):.2f}%')
    print(f'valuation_workers           : {profile.get("workers", 0)}')
    print(f'valuation_execution_mode    : {profile.get("execution_mode", "UNKNOWN")}')
    print(f'valuation_preload_seconds   : {profile.get("preload_seconds", 0)}')
    print(f'valuation_compute_seconds   : {profile.get("compute_seconds", 0)}')
    print(f'valuation_persist_seconds   : {profile.get("persist_seconds", 0)}')
    print()
    print('--- Governance ---')
    print(f'contract_status             : {contracts.get("status", "UNKNOWN")}')
    print(f'valuation_status            : {valuation.get("status", "UNKNOWN")}')
    print(f'valuation_built             : {valuation.get("built", 0)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
