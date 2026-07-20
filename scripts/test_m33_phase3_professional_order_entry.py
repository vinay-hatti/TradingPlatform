from pathlib import Path
from tempfile import TemporaryDirectory
from trading_ai.ui.models.paper_commands import GovernedActor
from trading_ai.ui.models.professional_order_entry import StrategyLeg, StrategyTicketRequest, ApprovalRequest
from trading_ai.ui.services.professional_order_entry_service import ProfessionalOrderEntryService

def main():
    trader=GovernedActor(user_id="trader",session_id="s1",roles=["TRADER"],permissions=["paper_orders.submit"])
    approver=GovernedActor(user_id="approver",session_id="s2",roles=["RISK_APPROVER"],permissions=["paper_orders.approve"])
    request=StrategyTicketRequest(
        account_id="paper",strategy_name="Bull Call Spread",contracts=2,net_limit_price=2.0,
        underlying_price=200,account_equity=100000,max_risk_pct=.02,reason="Paper spread test",
        actor=trader,legs=[
            StrategyLeg(leg_id="1",symbol="AAPL",option_expiry="2026-08-21",option_strike=200,option_type="CALL",side="BUY",bid=6,ask=6.2,delta=.52),
            StrategyLeg(leg_id="2",symbol="AAPL",option_expiry="2026-08-21",option_strike=205,option_type="CALL",side="SELL",bid=3.9,ask=4.1,delta=.35),
        ])
    with TemporaryDirectory() as d:
        svc=ProfessionalOrderEntryService(Path(d)/"tickets.json")
        preview=svc.preview(request)
        assert preview.strategy_type=="VERTICAL_SPREAD"
        assert preview.bounded_risk
        assert preview.maximum_loss is not None
        ticket=svc.create(request)
        assert ticket.status=="PENDING_APPROVAL"
        try:
            svc.approve(ticket.ticket_id,ApprovalRequest(decision="APPROVE",reason="Self approval",confirmation_token="CONFIRM-PAPER-123",actor=trader))
            raise AssertionError("self approval should fail")
        except PermissionError: pass
        approved=svc.approve(ticket.ticket_id,ApprovalRequest(decision="APPROVE",reason="Independent risk approval",confirmation_token="CONFIRM-PAPER-123",actor=approver))
        assert approved.status=="APPROVED"
    print("All Milestone 33 Phase 3 Professional Order Entry assertions passed.")
if __name__=="__main__": main()
