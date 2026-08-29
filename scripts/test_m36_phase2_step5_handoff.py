from trading_ai.portfolio_management.handoff_service import PortfolioExecutionHandoffService

def main():
    p=[{'candidate_id':'C1','symbol':'AAPL','strategy':'BULL_CALL_SPREAD','direction':'CALL','contracts':1,'recommended_allocation':500}]
    ready=PortfolioExecutionHandoffService().create(p,{'valid':True})
    assert ready.status=='READY_FOR_PRETRADE_RISK' and ready.order_count==1
    blocked=PortfolioExecutionHandoffService().create(p,{'valid':False})
    assert blocked.status=='BLOCKED' and blocked.order_count==0
    print('Milestone 36 Phase 2 Step 5 handoff assertions passed.')
if __name__=='__main__': main()
