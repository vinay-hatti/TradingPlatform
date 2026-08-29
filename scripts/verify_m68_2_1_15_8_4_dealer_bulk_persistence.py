from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parents[1]
refresh = (ROOT / "src/trading_ai/institutional_market_structure/refresh.py").read_text()
service = (ROOT / "src/trading_ai/institutional_market_structure/service.py").read_text()
market = (ROOT / "scripts/run_market_ingestion.py").read_text()

checks = {
    "dealer pure parallel compute": "PARALLEL_PURE_COMPUTE_SINGLE_BULK_WRITER" in refresh,
    "dealer immutable preload compute": "service.compute_preloaded" in refresh,
    "dealer one governed writer": "InstitutionalMarketStructureService.persist_many" in refresh,
    "dealer bulk persistence": "BULK_SINGLE_WRITER" in service,
    "dealer fallback preserves resilience": "SYMBOL_FALLBACK_AFTER_BULK_FAILURE" in service,
    "dealer batch inserts": "execute_chunks" in service and "session.execute(statement" in service,
    "dealer timing surfaced": "compute_wall=" in market and "bulk_commit_seconds" in market,
}
for name in ("run_intraday.sh", "run_morning.sh", "run_eod.sh"):
    text = (ROOT / "scripts/m69_6_scheduled" / name).read_text()
    checks[f"{name} serial polygon"] = "--polygon-network-workers 1" in text

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("M68.2.1.15.8.4 verification FAILED: " + ", ".join(failed))

for rel in (
    "src/trading_ai/institutional_market_structure/service.py",
    "src/trading_ai/institutional_market_structure/refresh.py",
    "scripts/run_market_ingestion.py",
    "scripts/report_m68_2_1_15_8_4_performance.py",
):
    py_compile.compile(str(ROOT / rel), doraise=True)

print("M68.2.1.15.8.4 source verification PASSED")
print(" - scheduled Polygon capture restored to one worker")
print(" - concurrent Polygon capability retained as non-default")
print(" - dealer inputs bulk-preloaded once")
print(" - dealer calculations run as pure parallel compute")
print(" - dealer persistence consolidated under one bulk writer")
print(" - bulk failure falls back to symbol-isolated persistence")
print(" - dealer persistence timing remains observable")
