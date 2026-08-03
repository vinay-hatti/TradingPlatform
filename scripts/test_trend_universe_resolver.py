from datetime import datetime, timezone
from trading_ai.market.trend_universe import TrendUniverseResolver, TrendUniverseType

class Result:
    def __init__(self, rows): self.rows=rows
    def mappings(self): return self
    def all(self): return self.rows
class Session:
    def __init__(self, rows): self.rows=rows
    def __enter__(self): return self
    def __exit__(self,*a): pass
    def execute(self,*a,**k): return Result(self.rows)

def factory(rows): return lambda: Session(rows)

def row(symbol, st, it, lt, **kw):
    return {"symbol":symbol,"short_term_state":st,"intermediate_term_state":it,"long_term_state":lt,"alignment_score":kw.get('a',.9),"trend_quality_score":kw.get('q',.9),"trend_confidence":kw.get('c',.9),"trend_stage":kw.get('stage','ESTABLISHED_TREND'),"relative_strength_vs_spy":kw.get('spy',.1),"relative_strength_vs_sector":kw.get('sector',.1),"snapshot_timestamp":datetime(2026,7,30,tzinfo=timezone.utc),"as_of_date":datetime(2026,7,30,tzinfo=timezone.utc).date(),"created_at":datetime(2026,7,30,tzinfo=timezone.utc)}

def main():
    rows=[row('AAA','STRONG_BULLISH','STRONG_BULLISH','STRONG_BULLISH'),row('BBB','PULLBACK','STRONG_BULLISH','STRONG_BULLISH'),row('CCC','STRONG_BEARISH','STRONG_BEARISH','STRONG_BEARISH',spy=-.1,sector=-.1)]
    r=TrendUniverseResolver(factory(rows))
    assert r.resolve(TrendUniverseType.STRONG_BULLISH_ALL.value,('AAA','BBB','CCC')).symbols==('AAA',)
    assert r.resolve(TrendUniverseType.PULLBACK_UPTREND.value,('AAA','BBB','CCC')).symbols==('BBB',)
    assert r.resolve(TrendUniverseType.STRONG_BEARISH_ALL.value,('AAA','BBB','CCC')).symbols==('CCC',)
    print('Trend universe resolver assertions passed.')
if __name__=='__main__': main()
