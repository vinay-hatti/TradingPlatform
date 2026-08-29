from datetime import datetime, timezone
from trading_ai.position_management.policy import PositionManagementPolicy
from trading_ai.position_management.service import PositionMonitoringService

def main():
    svc=PositionMonitoringService(PositionManagementPolicy(stale_mark_minutes=60))
    registry={"positions":[{"position_id":"P1","portfolio_id":"PRIMARY","symbol":"AAPL","strategy_type":"IRON_CONDOR","direction":"NEUTRAL","status":"OPEN","quantity":4,"entry_price":2.0,"opened_at":"2026-07-20T00:00:00+00:00","updated_at":"2026-07-22T00:00:00+00:00"}]}
    fresh={"marks":[{"position_id":"P1","symbol":"AAPL","price":2.1,"marked_at":"2026-07-22T00:00:00+00:00"}]}
    row=svc.assess(registry,fresh,{"trading_control":"REDUCE_ONLY"},datetime(2026,7,22,0,30,tzinfo=timezone.utc))[0]
    assert row.decision=="REDUCE" and row.urgency=="CRITICAL" and row.recommended_quantity==2
    stale={"marks":[{"position_id":"P1","symbol":"AAPL","price":2.1,"marked_at":"2026-07-21T00:00:00+00:00"}]}
    row=svc.assess(registry,stale,{"trading_control":"ALLOW"},datetime(2026,7,22,0,30,tzinfo=timezone.utc))[0]
    assert row.decision=="REVIEW" and "STALE_OR_INVALID_MARK" in row.reasons
    print("M39 risk and stale-data governance assertions passed.")
if __name__=="__main__": main()
