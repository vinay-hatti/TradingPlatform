from trading_ai.portfolio_management.allocation_service import PortfolioAwareCapitalAllocationService

def main():
    registry={'net_liquidation_value':100000,'cash_balance':80000,'positions':[{'status':'OPEN','capital_committed':10000}]}
    positions=[{'symbol':'AAPL','ranking_score':90,'expected_return_pct':60,'portfolio_fit_score':80,'capital_required':5000,'sector':'TECH'}, {'symbol':'MSFT','ranking_score':80,'expected_return_pct':40,'portfolio_fit_score':70,'capital_required':4000,'sector':'TECH'}]
    r=PortfolioAwareCapitalAllocationService().allocate(positions,registry)
    assert r.reserve_required==20000
    assert r.allocated_capital<=40000
    assert len(r.allocations)==2
    print('Milestone 36 Phase 2 Step 2 allocation assertions passed.')
if __name__=='__main__': main()
