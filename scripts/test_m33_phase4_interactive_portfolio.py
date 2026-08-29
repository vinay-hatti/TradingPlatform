import json
from pathlib import Path
from tempfile import TemporaryDirectory
from trading_ai.ui.models.interactive_portfolio import RebalanceConstraint, ScenarioRequest
from trading_ai.ui.services.interactive_portfolio_service import InteractivePortfolioService

def main():
    with TemporaryDirectory() as d:
        path=Path(d)/"state.json"
        path.write_text(json.dumps({"positions":[
            {"position_id":"p1","account_id":"paper-account","symbol":"AAPL","quantity":2,"average_price":5,"mark_price":6,"option_expiry":"2026-08-21","option_strike":200,"option_type":"CALL","delta":.5,"gamma":.02,"theta":-.1,"vega":.2,"underlying_price":200},
            {"position_id":"p2","account_id":"paper-account","symbol":"AAPL","quantity":-1,"average_price":3,"mark_price":2.5,"option_expiry":"2026-08-21","option_strike":210,"option_type":"CALL","delta":.3,"gamma":.01,"theta":-.05,"vega":.1,"underlying_price":200}
        ]}))
        svc=InteractivePortfolioService(path)
        summary=svc.summary()
        assert len(summary.positions)==2
        assert summary.net_delta==70
        assert summary.total_unrealized_pnl==250
        matrix=svc.exposure_matrix()
        assert len(matrix)==1
        scenarios=svc.scenarios(ScenarioRequest(underlying_shocks_pct=[-.05,.05],volatility_shocks_points=[0],days_forward=[0]))
        assert len(scenarios)==2
        proposal=svc.rebalance("paper-account",RebalanceConstraint(max_abs_delta=50))
        assert proposal.target_delta==50
        assert proposal.side=="SELL"
        assert proposal.phase3_handoff["requires_four_eye_approval"]
    print("All Milestone 33 Phase 4 Interactive Portfolio Management assertions passed.")
if __name__=="__main__": main()
