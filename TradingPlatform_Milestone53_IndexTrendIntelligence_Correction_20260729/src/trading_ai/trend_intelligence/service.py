from __future__ import annotations
import csv, json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from sqlalchemy import text
from trading_ai.database.session import SessionLocal
from trading_ai.persistence_normalization import strict_json_dumps
from .engine import TrendIntelligenceEngine

INDEX_MEMBERSHIP = {
    "SPX": ("Broad Market Index", "SPY"),
    "NDX": ("Technology Growth Index", "QQQ"),
    "RUT": ("Small Cap Index", "IWM"),
}

SECTOR_ETFS = {
    "Technology": "XLK", "Information Technology": "XLK",
    "Financial Services": "XLF", "Financials": "XLF",
    "Healthcare": "XLV", "Health Care": "XLV",
    "Consumer Cyclical": "XLY", "Consumer Discretionary": "XLY",
    "Consumer Defensive": "XLP", "Consumer Staples": "XLP",
    "Industrials": "XLI", "Energy": "XLE",
    "Basic Materials": "XLB", "Materials": "XLB",
    "Real Estate": "XLRE", "Utilities": "XLU",
    "Communication Services": "XLC",
}


class TrendIntelligenceService:
    def __init__(self, session_factory=SessionLocal, canonical_csv='data/universe/us_listed_equities_etfs.csv', engine=None):
        self.session_factory=session_factory; self.canonical_csv=Path(canonical_csv); self.engine=engine or TrendIntelligenceEngine()
    def _membership(self):
        out={}
        if self.canonical_csv.exists():
            with self.canonical_csv.open(newline='',encoding='utf-8-sig') as f:
                for r in csv.DictReader(f):
                    sym=(r.get('symbol') or '').strip(); sector=(r.get('sector') or '').strip() or 'Unknown'
                    if sym: out[sym]=(sector,SECTOR_ETFS.get(sector,''))
        # Indexes are governed canonical instruments even though the legacy CSV
        # is named for equities and ETFs. Add explicit index membership so the
        # base trend pipeline uses the same 613-instrument universe as ingestion.
        out.update({symbol: value for symbol, value in INDEX_MEMBERSHIP.items() if symbol not in out})
        return out
    def _prices(self,symbols):
        if not symbols:return {}
        with self.session_factory() as s:
            rows=[dict(r._mapping) for r in s.execute(text("SELECT symbol,date,close,volume FROM price_history WHERE symbol = ANY(:symbols) ORDER BY symbol,date"),{"symbols":list(symbols)})]
        out={}
        for r in rows:out.setdefault(r['symbol'],[]).append(r)
        return {k:pd.DataFrame(v) for k,v in out.items()}
    def build(self, symbols=None, persist=True):
        membership=self._membership(); targets=list(symbols or membership.keys()); refs={'SPY'}|{membership.get(s,('', ''))[1] for s in targets if membership.get(s,('', ''))[1]}
        data=self._prices(set(targets)|refs); results=[]; errors=[]; skipped=[]
        for symbol in targets:
            try:
                sector,etf=membership.get(symbol,('Unknown',''))
                snap=self.engine.analyze(symbol,data.get(symbol,pd.DataFrame()),benchmark=data.get('SPY'),sector_prices=data.get(etf),sector=sector,sector_etf=etf)
                results.append(snap)
            except Exception as exc:
                message=str(exc)
                if 'insufficient price history' in message.lower():
                    skipped.append({'symbol':symbol,'reason':'INSUFFICIENT_PRICE_HISTORY','detail':message})
                else:
                    errors.append({'symbol':symbol,'error':message})
        if persist:self.persist(results)
        status='READY' if results and not errors else 'DEGRADED' if results else 'FAILED'
        return {'status':status,'snapshot_timestamp':datetime.now(timezone.utc).isoformat(),'requested_symbol_count':len(targets),'symbol_count':len(results),'skipped_count':len(skipped),'error_count':len(errors),'results':[x.to_dict() for x in results],'skipped':skipped,'errors':errors}
    def persist(self,snapshots):
        with self.session_factory() as s:
            for snap in snapshots:
                p=snap.to_dict()
                s.execute(text("""INSERT INTO stock_trend_snapshot(snapshot_timestamp,symbol,as_of_date,short_term_state,intermediate_term_state,long_term_state,alignment_score,trend_quality_score,trend_confidence,trend_stage,trend_age_days,relative_strength_vs_spy,relative_strength_vs_sector,sector,sector_etf,calculation_version,payload_json,created_at) VALUES(:ts,:symbol,:asof,:st,:it,:lt,:a,:q,:c,:stage,:age,:spy,:sec,:sector,:etf,:v,:p,:ts) ON CONFLICT(snapshot_timestamp,symbol) DO UPDATE SET payload_json=EXCLUDED.payload_json,alignment_score=EXCLUDED.alignment_score,trend_quality_score=EXCLUDED.trend_quality_score,trend_confidence=EXCLUDED.trend_confidence"""),{'ts':snap.snapshot_timestamp,'symbol':snap.symbol,'asof':snap.as_of_date,'st':snap.short_term.state,'it':snap.intermediate_term.state,'lt':snap.long_term.state,'a':snap.alignment_score,'q':snap.trend_quality_score,'c':snap.trend_confidence,'stage':snap.trend_stage,'age':snap.trend_age_days,'spy':snap.relative_strength_vs_spy,'sec':snap.relative_strength_vs_sector,'sector':snap.sector,'etf':snap.sector_etf,'v':snap.calculation_version,'p':strict_json_dumps(p)})
            s.commit()
