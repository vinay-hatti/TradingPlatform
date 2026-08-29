from __future__ import annotations
import argparse,csv
from datetime import date
from pathlib import Path
from trading_ai.database import SessionLocal
from trading_ai.scanner.market_data_quality.quality import MarketDataQualityPolicy,MarketDataQualityService
from trading_ai.scanner.market_data_quality.quality_serialization import write_quality_csv,write_quality_json
def load_symbols(path):
    with Path(path).open(newline="",encoding="utf-8-sig") as h:
        r=csv.DictReader(h); fields=r.fieldnames or []
        sk=next((x for x in fields if x.strip().lower()=="symbol"),None)
        if sk is None: raise ValueError(f"Canonical CSV must contain symbol column: {path}")
        ak=next((x for x in fields if x.strip().lower()=="active"),None); out=[]
        for row in r:
            if ak:
                a=str(row.get(ak,"")).strip().lower()
                if a and a not in {"1","true","yes","y"}: continue
            s=str(row.get(sk,"")).strip().upper()
            if s: out.append(s)
    return sorted(set(out))
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--canonical-csv",default="data/universe/us_listed_equities_etfs.csv")
    p.add_argument("--as-of-date",default=date.today().isoformat())
    p.add_argument("--lookback-rows",type=int,default=252)
    p.add_argument("--extreme-return-threshold",type=float,default=.50)
    p.add_argument("--output-directory",default="reports/m35/phase2/quality")
    a=p.parse_args(); symbols=load_symbols(a.canonical_csv)
    session=SessionLocal()
    try:
        profile=MarketDataQualityService(session,MarketDataQualityPolicy(lookback_rows=a.lookback_rows,extreme_return_threshold=a.extreme_return_threshold)).evaluate(symbols,date.fromisoformat(a.as_of_date))
    finally: session.close()
    out=Path(a.output_directory)
    jp=write_quality_json(profile,out/"market_data_quality.json")
    cp=write_quality_csv(profile,out/"market_data_symbol_quality.csv")
    print("="*65); print("Milestone 35 Phase 2 Market Data OHLCV Quality"); print("="*65)
    for label,value in [
        ("Canonical Symbols",profile.canonical_symbol_count),("Evaluated Symbols",profile.evaluated_symbol_count),
        ("READY Symbols",profile.ready_symbol_count),("DEGRADED Symbols",profile.degraded_symbol_count),
        ("REVIEW Symbols",profile.review_symbol_count),("FAILED Symbols",profile.failed_symbol_count),
        ("Symbols With Invalid Rows",profile.symbols_with_invalid_rows),
        ("Symbols With Extreme Returns",profile.symbols_with_extreme_returns),
        ("Invalid Price Rows",profile.total_invalid_price_rows),("Invalid OHLC Rows",profile.total_invalid_ohlc_rows),
        ("Negative Volume Rows",profile.total_negative_volume_rows),("Zero Volume Rows",profile.total_zero_volume_rows),
        ("Non-Finite Rows",profile.total_non_finite_rows),("Extreme Return Rows",profile.total_extreme_return_rows)]:
        print(f"{label:<32}{value:>10}")
    print(f"{'Average Quality Score':<32}{profile.average_quality_score:>10.2f}")
    print(f"{'Minimum Quality Score':<32}{profile.minimum_quality_score:>10.2f}")
    print(f"{'Quality Status':<32}{profile.status.value:>10}")
    print(f"JSON Report                    {jp}"); print(f"Symbol CSV                     {cp}")
if __name__=="__main__": main()
