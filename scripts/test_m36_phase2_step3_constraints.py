from trading_ai.portfolio_management.constraint_service import PortfolioConstraintValidationService

def main():
    registry={'net_liquidation_value':100000,'positions':[]}
    ok=PortfolioConstraintValidationService().validate([{'symbol':'AAPL','sector':'TECH','strategy':'SPREAD','direction':'CALL','correlation_group':'MEGA','recommended_allocation':5000,'delta':10}],registry)
    assert ok.valid
    bad=PortfolioConstraintValidationService().validate([{'symbol':'AAPL','sector':'TECH','strategy':'SPREAD','direction':'CALL','correlation_group':'MEGA','recommended_allocation':20000,'delta':600}],registry)
    codes={x['code'] for x in bad.violations}
    assert 'SYMBOL_EXPOSURE_LIMIT_EXCEEDED' in codes and 'DELTA_LIMIT_EXCEEDED' in codes
    print('Milestone 36 Phase 2 Step 3 constraint assertions passed.')
if __name__=='__main__': main()
