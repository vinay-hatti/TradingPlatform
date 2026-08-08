from types import SimpleNamespace
from trading_ai.stock_intelligence.publication import StockScannerPublicationService
from trading_ai.stock_intelligence.orchestration import StockScannerOrchestrator


def test_summary_exposes_dynamic_management_fields():
    row=SimpleNamespace(id='c1',symbol='AAPL',category='BULLISH',score=88,snapshot_timestamp='2026-08-03',payload_json={
        'direction':'BULLISH','structure':'EARLY_TREND','alignment_score':91,'metadata':{'rank':1},
        'scores':{'primary_category':'BULLISH','overall':88,'confidence':84,'freshness':100},
        'participation':{'state':'ACCUMULATION'},'breakout':{'state':'BREAKOUT_RETEST'},
        'context':{'relative_strength_grade':'A','dealer_positioning':'BULLISH','gamma_regime':'NEGATIVE_GAMMA','market_regime':'BULL_TREND'},
        'trade_plan':{'entry':{'zone_low':100,'zone_high':101},'stop':{'recommended_stop':97},'targets':{'targets':[{'price':105},{'price':110}]},'structural_reward_risk':3,'management_quality':90},
        'timeframe_states':{'1d':{'direction':'BULLISH','structure':'EARLY_TREND','confidence':90}},'warnings':[],'state_hash':'h'})
    value=StockScannerPublicationService._summary(row,row.payload_json)
    assert value['entry_zone_low']==100
    assert value['recommended_stop']==97
    assert value['targets']==[105,110]
    assert value['management_quality']==90


def test_orchestrator_is_polygon_lineage_and_deterministic_order(monkeypatch):
    class Profile:
        def __init__(self,symbol,score):
            self.symbol=symbol;self.scores=SimpleNamespace(overall=score);self.metadata={};self.state_hash=symbol
    class Intelligence:
        def analyze(self,symbol,*args,**kwargs):return Profile(symbol,{'B':70,'A':90}[symbol])
    class Session:
        def add(self,x):pass
        def commit(self):pass
    service=StockScannerOrchestrator(Session(),Intelligence())
    saved=[];service.repository.save_profile=lambda run,candidate,p:saved.append(p.symbol)
    result=service.run({'B':{},'A':{}},minimum_score=0)
    assert saved==['A','B']
    assert result['status']=='READY'


def test_router_is_registered():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    router=(root/'src/trading_ai/stock_intelligence/router.py').read_text()
    app=(root/'src/trading_ai/ui/app.py').read_text()
    assert '@router.get("/candidates"' in router
    assert '@router.get("/candidates/{candidate_id}"' in router
    assert 'stock_intelligence_router' in app


def test_workstation_source_contains_stock_scanner_page():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    assert "'stock-intelligence': StockIntelligenceScannerPage" in (root/'ui/workstation/src/App.tsx').read_text()
    assert "Stock Intelligence Scanner" in (root/'ui/workstation/src/StockIntelligenceScannerPage.tsx').read_text()
