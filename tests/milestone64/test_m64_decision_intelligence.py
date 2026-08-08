from trading_ai.portfolio_risk_allocation.decision_intelligence import InstitutionalDecisionIntelligenceService


def service():
    return InstitutionalDecisionIntelligenceService.__new__(InstitutionalDecisionIntelligenceService)


def test_correlation_and_decision_policy():
    svc=service()
    a={str(i):i/100 for i in range(20)}; b={str(i):i/50 for i in range(20)}
    assert svc._corr(a,b) > .99
    assert svc._decision(80,'ACCEPT',{'after':{'portfolio_heat_pct':10}})=='ACCEPT'
    assert svc._decision(50,'ACCEPT',{'after':{'portfolio_heat_pct':10}})=='REJECT'


def test_marginal_impact_has_before_after_and_signed_greeks():
    svc=service()
    risk={'net_liquidation':100000,'var_95':1000,'portfolio_heat_pct':5,'payload_json':{'greeks':{'delta':10,'gamma':2,'theta':-3,'vega':5},'capital':{'capital_usage_pct':10}}}
    value=svc._marginal_impact(risk,1000,{'delta':.5,'gamma':.1,'theta':-.2,'vega':.3,'rho':0},0.2)
    assert value['marginal_greeks']['delta']==50
    assert value['after']['delta']==60
    assert value['marginal_heat_pct']==1


def test_explainability_is_canonical():
    svc=service()
    item={'fit':{'portfolio_fit_score':90,'reasons':['PORTFOLIO_DIVERSIFICATION_ACCEPTABLE']},'correlation':.1,'diversification_benefit':90,'capital_efficiency':60,'marginal':{'after':{'portfolio_heat_pct':8}}}
    value=svc._explain(item,95,'ACCEPT',1)
    assert value['positive_reasons']
    assert value['risk_reasons']==[]
