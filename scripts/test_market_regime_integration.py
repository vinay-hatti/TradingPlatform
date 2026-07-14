from types import SimpleNamespace
from trading_ai.strategy_engine.market_regime_integration_service import MarketRegimeIntegrationService

def main():
 s=MarketRegimeIntegrationService()
 bull=SimpleNamespace(valid=True,current_regime="BULL_TREND",regime_score=82,severity="LOW")
 fc=SimpleNamespace(forecast_regime="BULL_TREND",forecast_score=79,transition_probability=.1)
 br=SimpleNamespace(portfolio_regime="BULL_TREND",breadth_score=76)
 a=s.integrate(symbol="AAPL",direction="CALL",strategy="BULL_PUT_SPREAD",strategy_score=70,ranking_score=72,regime_profile=bull,forecast_profile=fc,breadth_profile=br)
 assert a.valid and a.allowed and a.strategy_alignment=="ALIGNED" and a.adapted_strategy_score>70
 o=s.integrate(symbol="AAPL",direction="PUT",strategy="BEAR_CALL_SPREAD",strategy_score=70,ranking_score=72,regime_profile=bull,forecast_profile=fc,breadth_profile=br)
 assert o.strategy_alignment=="OPPOSED" and o.adapted_strategy_score<70
 print("All market-regime integration assertions passed.")
if __name__=="__main__": main()
