from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import text

from trading_ai.database.session import SessionLocal
from trading_ai.trend_intelligence.institutional_service import InstitutionalTrendService


INDEX_SYMBOLS = ("SPX", "NDX", "RUT")


def canonical_symbols(path: str) -> list[str]:
    p = Path(path)
    if p.exists():
        import pandas as pd
        frame = pd.read_csv(p)
        col = "symbol" if "symbol" in frame.columns else frame.columns[0]
        values = list(frame[col].dropna().astype(str).str.strip().str.upper())
        return list(dict.fromkeys(values + list(INDEX_SYMBOLS)))
    with SessionLocal() as session:
        return [str(v).upper() for v in session.execute(text("SELECT DISTINCT symbol FROM price_history ORDER BY symbol")).scalars()]


def main():
    parser = argparse.ArgumentParser(description="Populate Milestone 52 Phase 4 institutional trend intelligence")
    parser.add_argument("--symbols", default="")
    parser.add_argument("--canonical-csv", default="data/universe/us_listed_equities_etfs.csv")
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end", required=True)
    parser.add_argument("--report", default="reports/trend_intelligence/institutional_latest.json")
    args = parser.parse_args()
    symbols = [x.strip().upper() for x in args.symbols.split(",") if x.strip()] or canonical_symbols(args.canonical_csv)
    payload = InstitutionalTrendService().run(symbols, args.start, args.end, args.report)
    print(json.dumps({k: payload[k] for k in ["status", "snapshot_timestamp", "requested_symbol_count", "symbol_count", "skipped_count", "error_count"]}, indent=2))
    print(args.report)


if __name__ == "__main__":
    main()
