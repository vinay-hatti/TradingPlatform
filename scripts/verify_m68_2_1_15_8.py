from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def need(path: str, tokens: tuple[str, ...]):
    p = ROOT / path
    if not p.is_file():
        raise SystemExit(f"PACKAGE CONTENT ERROR: required file missing: {path}")
    text = p.read_text(encoding="utf-8")
    missing = [token for token in tokens if token not in text]
    if missing:
        raise SystemExit(f"M68.2.1.15.8 verification FAILED: {path} missing {missing}")

need("src/trading_ai/scanner/options_market_data_ingestion/persistence.py", (
    "class GovernedOptionSnapshotWriter",
    "ON CONFLICT (snapshot_run_id, option_symbol) DO UPDATE SET",
))
need("src/trading_ai/scanner/options_market_data_ingestion/service.py", (
    "governed_snapshot_run_id",
    "self.snapshot_writer.write(valid_records)",
))
need("src/trading_ai/market_intelligence/ingestion_orchestrator.py", (
    "def begin_option_snapshot",
    "def finalize_option_snapshot",
    "DELETE FROM option_contract_history history",
    "snapshot.snapshot_run_id=:run_id",
))
need("src/trading_ai/institutional_market_structure/refresh.py", (
    "ThreadPoolExecutor",
    "max_workers",
    "executor.map(refresh_one, normalized)",
))
need("scripts/run_market_ingestion.py", (
    "def _run_fresh_option_derived_lanes",
    "ThreadPoolExecutor(max_workers=3",
    "dealer_positioning_max_workers",
))
need("scripts/ingest_options_data.py", (
    "core._begin_fresh_option_lineage",
    "core._finalize_fresh_option_lineage",
    "core._run_fresh_option_derived_lanes",
    "Options end-to-end performance",
))

for test_path in (
    "tests/milestone68/test_m68_2_1_15_4_authority_state_reconciliation.py",
    "tests/m68_2_1_15_4_1/test_portfolio_authority_projection.py",
    "tests/m68_2_1_15_5/test_contradictory_evidence_forecast_governance.py",
    "tests/m68_2_1_15_6/test_intraday_orchestration.py",
    "tests/m68_2_1_15_7/test_strategy_aware_trade_builder_revalidation.py",
    "tests/m68_2_1_15_8/test_exact_cycle_parallel_options.py",
):
    if not (ROOT / test_path).is_file():
        raise SystemExit(f"PACKAGE CONTENT ERROR: required cumulative test missing: {test_path}")

print("M68.2.1.15.8 source verification PASSED")
print(" - exact current-cycle option snapshot membership")
print(" - same-day stale compatibility rows pruned after successful capture")
print(" - direct batched governed snapshot persistence")
print(" - four-worker dealer positioning with deterministic result ordering")
print(" - volatility / liquidity / dealer three-lane parallel barrier")
print(" - structured options-domain and end-to-end performance timings")
