from __future__ import annotations

from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trading_ai.database.base import Base
from trading_ai.market.models import PriceHistory
from trading_ai.market.option_models import OptionContractHistory
from trading_ai.institutional_options.contract_optimization import (
    ContractOptimizationPolicy,
    ExactPolygonContractOptimizer,
    InstitutionalContractOptimizationService,
    OptionContractRecord,
)
from trading_ai.institutional_options.domain import (
    InstitutionalOpportunity, OpportunityLineage, OpportunityState, OpportunityThesis,
    StrategyCandidate, StrategyDisposition, ThesisDirection,
)
from trading_ai.institutional_options.models import (
    ContractRecommendationModel, InstitutionalOpportunityModel,
)
from trading_ai.institutional_options.repository import InstitutionalOpportunityRepository
from trading_ai.institutional_options.strategy_generation import InstitutionalStrategyGenerationService


def record(symbol, expiry, strike, kind, delta):
    return OptionContractRecord(symbol, date(2026,8,4), expiry, kind, strike, 1.0, 1.1, 1.05, 100, 500, .25, delta, .02, -.04, .12)


def candidate(strategy):
    return StrategyCandidate(f"sc-{strategy}", "opp-1", strategy, StrategyDisposition.ELIGIBLE, 80, rank=1)


def chain():
    q=date(2026,8,4); e1=q+timedelta(days=30); e2=q+timedelta(days=60); e3=q+timedelta(days=90)
    rows=[]
    for e in (e1,e2,e3):
        for strike,cd,pd in [(90,.8,-.2),(95,.65,-.35),(100,.52,-.48),(105,.35,-.65),(110,.2,-.8)]:
            rows.append(record(f"O:AAPL{e:%y%m%d}C{int(strike*1000):08d}",e,strike,"CALL",cd))
            rows.append(record(f"O:AAPL{e:%y%m%d}P{int(strike*1000):08d}",e,strike,"PUT",pd))
    return rows


def test_long_call_uses_exact_polygon_identity():
    r=ExactPolygonContractOptimizer().optimize(candidate("LONG_CALL"),chain(),100,"snap")
    assert r.executable and len(r.legs)==1 and r.legs[0].option_symbol.startswith("O:AAPL")


def test_bull_call_spread_same_expiry_and_ordered_strikes():
    r=ExactPolygonContractOptimizer().optimize(candidate("BULL_CALL_SPREAD"),chain(),100,"snap")
    assert r.executable and len({x.expiry for x in r.legs})==1
    assert r.legs[0].strike < r.legs[1].strike


def test_calendar_uses_distinct_expirations():
    r=ExactPolygonContractOptimizer().optimize(candidate("CALL_CALENDAR"),chain(),100,"snap")
    assert r.executable and len({x.expiry for x in r.legs})==2


def test_iron_condor_has_four_distinct_legs():
    r=ExactPolygonContractOptimizer().optimize(candidate("IRON_CONDOR"),chain(),100,"snap")
    assert r.executable and len(r.legs)==4
    assert len({x.option_symbol for x in r.legs})==4


def test_missing_contracts_is_non_executable():
    r=ExactPolygonContractOptimizer().optimize(candidate("LONG_CALL"),[],100,"snap")
    assert not r.executable and not r.legs


def seed(session):
    opp=InstitutionalOpportunity("opp-1","AAPL","EQUITY",OpportunityState.VALIDATED,ThesisDirection.BULLISH,"TREND_CONTINUATION",88,84,"HIGH",OpportunityLineage("current_stock_intelligence","run","cand","hash"),"thesis-1")
    thesis=OpportunityThesis("thesis-1","opp-1",ThesisDirection.BULLISH,"TREND_CONTINUATION","1d","UPTREND","LEADING","BULLISH","TRENDING","ACCUMULATION","POSITIVE_GAMMA","BULLISH",99,100,95,(108,112))
    InstitutionalOpportunityRepository(session).save_opportunity(opp,thesis)
    InstitutionalStrategyGenerationService(session).generate()
    session.add(PriceHistory(symbol="AAPL",date=date(2026,8,4),open=99,high=101,low=98,close=100,volume=1000000))
    for row in chain():
        session.add(OptionContractHistory(underlying_symbol="AAPL",option_symbol=row.option_symbol,quote_date=row.quote_date,expiry=row.expiry,option_type=row.option_type,strike=row.strike,bid=row.bid,ask=row.ask,mid=row.midpoint,last=row.last,volume=row.volume,open_interest=row.open_interest,implied_volatility=row.implied_volatility,delta=row.delta,gamma=row.gamma,theta=row.theta,vega=row.vega,rho=0))
    session.flush()


def test_service_persists_and_transitions():
    engine=create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session)
        result=InstitutionalContractOptimizationService(session).optimize()
        session.commit()
        assert result.optimized==1 and result.executable_recommendations>=1
        assert session.query(ContractRecommendationModel).count()>=1
        assert session.get(InstitutionalOpportunityModel,"opp-1").state==OpportunityState.CONTRACTS_OPTIMIZED.value


def test_service_isolates_missing_option_data():
    engine=create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        opp=InstitutionalOpportunity("opp-1","AAPL","EQUITY",OpportunityState.VALIDATED,ThesisDirection.BULLISH,"TREND_CONTINUATION",88,84,"HIGH",OpportunityLineage("p","r","c","h"),"thesis-1")
        thesis=OpportunityThesis("thesis-1","opp-1",ThesisDirection.BULLISH,"TREND_CONTINUATION","1d","UPTREND",None,"BULLISH","TRENDING",None,None,None,99,100,95,(108,))
        InstitutionalOpportunityRepository(session).save_opportunity(opp,thesis)
        InstitutionalStrategyGenerationService(session).generate()
        result=InstitutionalContractOptimizationService(session).optimize()
        assert result.failed==1 and result.optimized==0


def test_policy_filters_wide_spreads():
    rows=chain(); bad=rows[0]
    bad=OptionContractRecord(bad.option_symbol,bad.quote_date,bad.expiry,bad.option_type,bad.strike,.1,3,1,100,500,.25,bad.delta,.02,-.04,.12)
    assert bad.spread_pct > ContractOptimizationPolicy().maximum_spread_pct


def test_contract_api_routes_registered():
    from pathlib import Path
    source=Path("src/trading_ai/institutional_options/router.py").read_text()
    assert '@router.post("/contracts/optimize"' in source
    assert '@router.get("/opportunities/{opportunity_id}/contracts"' in source


def test_existing_scanner_pages_unchanged():
    from pathlib import Path
    source=Path("ui/workstation/src/pages.tsx").read_text()
    assert "Daily scanner" in source
    assert "Option scanner" in source
