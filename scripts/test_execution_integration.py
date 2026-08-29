from datetime import datetime, timedelta
from types import SimpleNamespace
from trading_ai.strategy_engine.execution_analytics_profile import ExecutionFill
from trading_ai.strategy_engine.execution_integration_service import ExecutionIntegrationService


def main():
    now=datetime(2026,7,14,10,0)
    fills=[]
    for i,(venue,broker,price) in enumerate([("CBOE","BROKER_A",2.002),("ISE","BROKER_B",2.004),("CBOE","BROKER_A",2.001),("ISE","BROKER_B",2.005)]):
        fills.append(ExecutionFill(order_id=f"O{i}",symbol="AAPL",side="BUY",quantity_requested=1,quantity_filled=1,decision_price=2.0,arrival_price=2.001,fill_price=price,bid=1.998,ask=2.006,submitted_at=now,filled_at=now+timedelta(seconds=2+i),venue=venue,metadata={"broker":broker,"vwap":2.002}))
    service=ExecutionIntegrationService()
    profile=service.analyze(fills)
    assert profile.valid and profile.order_count==4
    assert profile.recommended_venue != "UNAVAILABLE"
    d=SimpleNamespace(symbol="AAPL",allowed=True,warnings=[],rejection_reasons=[],metadata={})
    service.attach([d],profile)
    assert d.execution_analytics_valid is True
    assert d.execution_integration_profile is profile
    assert "execution_integration_profile" in d.metadata
    empty=service.analyze([])
    assert not empty.valid and empty.allowed
    print("All execution integration assertions passed.")

if __name__=="__main__": main()
