import json
from types import SimpleNamespace
from trading_ai.strategy_engine.risk_surface_service import RiskSurfaceService
from trading_ai.strategy_engine.risk_surface_serialization import risk_surface_to_dict


def profile(service,symbol,delta,gamma,vega,theta,capital):
    return service.analyze_strategy(symbol=symbol,strategy="TEST_SPREAD",underlying_price=100.0,implied_volatility=0.30,days_to_expiration=30,capital_required=capital,initial_capital=100000.0,net_delta=delta,net_gamma=gamma,net_vega=vega,net_theta=theta,net_rho=0.0)

def main():
    service=RiskSurfaceService()
    a=profile(service,"AAPL",20,0.5,-30,5,5000)
    b=profile(service,"MSFT",-10,0.3,20,3,4000)
    p=service.analyze_portfolio([a,b],100000.0,allocations=[2.0,1.0],position_metadata=[{"position_id":"A1","sector":"TECH","correlation_group":"MEGA_TECH"},{"position_id":"M1","sector":"TECH","correlation_group":"MEGA_TECH"}])
    assert p.valid and p.position_count==2 and p.point_count>0
    assert p.total_allocated_capital==14000.0
    assert abs(sum(x.loss_contribution_pct for x in p.position_contributions)-1.0)<1e-9 or p.worst_case_pnl>=0
    assert 0<=p.loss_concentration_score<=1 and p.effective_position_count>0
    assert len(p.factor_attributions)==5 and len(p.sector_contributions)==1
    payload=risk_surface_to_dict(p); json.dumps(payload); assert payload["position_contributions"][0]["position_id"]
    legacy=service.analyze_portfolio([a,b],100000.0); assert legacy.valid
    print("All portfolio risk-surface assertions passed.")

if __name__=="__main__": main()
