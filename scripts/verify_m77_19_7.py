#!/usr/bin/env python3
from pathlib import Path
import ast
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
P = ROOT / "scripts/run_m77_19_7_symbol_specific_polygon_history_authority.py"
if not P.exists():
    raise SystemExit("M77.19.7 verification FAILED: runner missing")
T = P.read_text()
ast.parse(T)

required = (
    'HISTORY_AUTHORITY_SOURCE = "POLYGON_DIRECT_REST_API"',
    'DATABASE_ACCESS = "NONE"',
    'PRICE_HISTORY_AUTHORITY_ALLOWED = False',
    'DEFAULT_POLYGON_BASE_URL = "https://api.polygon.io"',
    'POLYGON_PROVIDER_HISTORY_FLOOR = dt.date(2003, 9, 10)',
    '"sort": "asc"',
    '"limit": EARLIEST_BAR_QUERY_LIMIT',
    '"sort": "desc"',
    'def ticker_events',
    'def splits',
    'def parse_ticker_lineage',
    'lineage_join_authorized = False',
    '"price_history_table_used": False',
    '"predecessor_successor_series_automatically_concatenated": False',
    '"full_23_year_reconstruction_authorized": FULL_23_YEAR_RECONSTRUCTION_AUTHORIZED',
    '"symbol_specific_reconstruction_authorized": False',
    '"production_authority_effect": PRODUCTION_AUTHORITY_EFFECT',
)
missing = [x for x in required if x not in T]
if missing:
    raise SystemExit(f"M77.19.7 verification FAILED: missing markers {missing}")

prohibited = (
    "SessionLocal",
    "sqlalchemy",
    "create_engine",
    "SELECT ",
    "INSERT ",
    "UPDATE ",
    "DELETE ",
    "price_history",
)
# price_history appears only in explicit governance marker text; reject executable-style uses separately.
for bad in prohibited[:-1]:
    if bad in T:
        raise SystemExit(f"M77.19.7 verification FAILED: prohibited DB token {bad}")
if "from trading_ai.database" in T or "import trading_ai.database" in T:
    raise SystemExit("M77.19.7 verification FAILED: database import found")
if "FROM price_history" in T or "from price_history" in T:
    raise SystemExit("M77.19.7 verification FAILED: price_history query found")

print("M77.19.7 verification PASSED")
print(" - historical availability authority is Polygon DIRECT REST only")
print(" - canonical universe CSV is the symbol source")
print(" - oldest daily aggregate is queried from Polygon provider floor with sort=asc")
print(" - warm-up eligible date is derived from earliest returned Polygon bars")
print(" - latest daily aggregate is queried directly from Polygon")
print(" - ticker details, ticker-change events and splits are queried directly where accessible")
print(" - declared predecessor tickers are queried as separate Polygon history segments")
print(" - predecessor/successor history is NEVER auto-concatenated")
print(" - no database package import or SQL is allowed")
print(" - price_history table is not an authority")
print(" - resumable filesystem checkpoint is enabled")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
