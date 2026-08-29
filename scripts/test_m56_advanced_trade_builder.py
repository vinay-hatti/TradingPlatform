from trading_ai.advanced_trade_builder.contracts import TradeLeg,LegSide,OptionRight
from trading_ai.advanced_trade_builder.service import AdvancedTradeBuilderService
legs=(TradeLeg(LegSide.BUY,1,OptionRight.CALL,100,'2026-09-18',5,0.55,0.02,-0.08,0.15),TradeLeg(LegSide.SELL,1,OptionRight.CALL,110,'2026-09-18',2,0.30,0.01,-0.04,0.09))
debit,credit,loss,profit,rr,budget,greeks,checks=AdvancedTradeBuilderService.economics(legs,100000,1)
assert debit==500 and credit==200 and loss==300 and profit==700 and round(rr,2)==2.33
assert budget==1000 and checks['valid'] and round(greeks['delta'],2)==0.25
bad=(TradeLeg(LegSide.BUY,10,OptionRight.CALL,100,'2026-09-18',20),)
assert not AdvancedTradeBuilderService.economics(bad,10000,1)[7]['risk_within_budget']
print('Milestone 56 Advanced Trade Builder assertions passed.')
