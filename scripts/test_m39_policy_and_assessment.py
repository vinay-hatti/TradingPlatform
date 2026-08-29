from datetime import datetime, timezone
from trading_ai.position_management.policy import PositionManagementPolicy
from trading_ai.position_management.service import PositionMonitoringService

def main():
    svc=PositionMonitoringService(PositionManagementPolicy(stale_mark_minutes=120))
    registry={"positions":[
      {"position_id":"P1","portfolio_id":"PRIMARY","symbol":"AAPL","strategy_type":"LONG_CALL","direction":"BULLISH","status":"OPEN","quantity":2,"entry_price":2.0,"current_price":2.0,"opened_at":"2026-07-01T00:00:00+00:00","updated_at":"2026-07-22T00:00:00+00:00"},
      {"position_id":"P2","portfolio_id":"PRIMARY","symbol":"MSFT","strategy_type":"LONG_PUT","direction":"BEARISH","status":"OPEN","quantity":1,"entry_price":4.0,"current_price":4.0,"opened_at":"2026-07-01T00:00:00+00:00","updated_at":"2026-07-22T00:00:00+00:00"}]}
    marks={"marks":[{"position_id":"P1","symbol":"AAPL","price":3.2,"marked_at":"2026-07-22T00:00:00+00:00"},{"position_id":"P2","symbol":"MSFT","price":2.4,"marked_at":"2026-07-22T00:00:00+00:00"}]}
    rows=svc.assess(registry,marks,{},datetime(2026,7,22,0,30,tzinfo=timezone.utc))
    assert rows[0].decision=="CLOSE" and "TAKE_PROFIT_TRIGGERED" in rows[0].reasons
    assert rows[1].decision=="CLOSE" and "STOP_LOSS_TRIGGERED" in rows[1].reasons
    print("M39 policy and assessment assertions passed.")
if __name__=="__main__": main()
