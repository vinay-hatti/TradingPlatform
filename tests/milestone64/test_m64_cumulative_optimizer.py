from types import SimpleNamespace
from trading_ai.portfolio_risk_allocation.optimizer import PortfolioOptimizationService


def svc():
    return PortfolioOptimizationService.__new__(PortfolioOptimizationService)


def risk():
    return {
        'snapshot_id':'risk-1','net_liquidation':100000.0,'buying_power':300000.0,
        'portfolio_heat_pct':5.0,'var_95':1000.0,'expected_shortfall_95':1250.0,
        'capital_committed':5000.0,
        'payload_json':{
            'greeks':{'delta':20,'gamma':2,'theta':-5,'vega':8,'beta_weighted_delta':5000},
            'capital':{'capital_usage_pct':5},
            'exposures':{'symbol':{'AAPL':1000},'sector':{'Technology':1000},'strategy':{'BULL_CALL_SPREAD':1000}},
        },
    }


def decision(opportunity,symbol,sector,score=90,capital=1000,corr=.1):
    payload={
        'symbol':symbol,'sector':sector,'strategy':'BULL_CALL_SPREAD',
        'decision_identity':{'opportunity_id':opportunity,'institutional_decision_snapshot_id':'ds-'+opportunity},
        'scores':{'final_portfolio_score':score,'portfolio_fit_score':92,'opportunity_cost_score':88},
        'capital_allocation':{'recommended_quantity':1,'recommended_capital':capital},
        'portfolio_impact':{'marginal_heat_pct':1,'marginal_var_95':50,'marginal_greeks':{'delta':10,'gamma':1,'theta':-1,'vega':2}},
        'correlation':{'portfolio_correlation':corr},
        'explainability':{'positive_reasons':['good']},
    }
    return SimpleNamespace(opportunity_id=opportunity,decision='ACCEPT',rank=1,final_portfolio_score=score,payload_json=payload)


def test_optimizer_selects_best_candidates_under_constraints():
    service=svc(); policy=dict(PortfolioOptimizationService.DEFAULT_POLICY)
    budgets=service._risk_budgets(risk(),policy)
    selected,rejected=service._select_candidates([
        decision('one','XOM','Energy',95),decision('two','WFC','Financials',90)
    ],risk(),budgets,policy)
    assert [row['opportunity_id'] for row in selected]==['one','two']
    assert rejected==[]


def test_optimizer_rejects_high_correlation():
    service=svc();policy=dict(PortfolioOptimizationService.DEFAULT_POLICY)
    budgets=service._risk_budgets(risk(),policy)
    selected,rejected=service._select_candidates([decision('one','MSFT','Technology',90,corr=.95)],risk(),budgets,policy)
    assert selected==[]
    assert 'CORRELATION_LIMIT' in rejected[0]['rejection_reasons']


def test_target_portfolio_aggregates_before_after():
    service=svc()
    target=service._target_portfolio(risk(),[{'recommended_capital':1000,'marginal_var_95':50,'marginal_heat_pct':1,'marginal_greeks':{'delta':10}}])
    assert target['after']['greeks']['delta']==30
    assert target['after']['var_95']==1050


def test_m64_cumulative_models_registered():
    from trading_ai.database.base import Base
    import trading_ai.database.models
    for table in ('portfolio_risk_budget_snapshots','portfolio_optimization_snapshots','portfolio_action_recommendations','portfolio_allocation_publications'):
        assert table in Base.metadata.tables


def test_m64_cumulative_migration_chain():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    text=(root/'migrations/versions/m64_003_cumulative_portfolio_optimization.py').read_text()
    assert "down_revision='m64_002'" in text
