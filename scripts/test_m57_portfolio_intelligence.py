from trading_ai.portfolio_intelligence.contracts import PositionMark,PositionAction
from trading_ai.portfolio_intelligence.service import PortfolioIntelligenceService
def main():
 good=PositionMark(5,2,1000,200,25,.6,.03,-.2,.12,30);h=PortfolioIntelligenceService.health(good,{'thesis_score':92});d=PortfolioIntelligenceService.decision(good,h);assert h.score>75;assert d.action==PositionAction.HOLD
 bad=PositionMark(.5,2,100,-900,-90,2,.01,-2,.2,2);h2=PortfolioIntelligenceService.health(bad,{'thesis_score':30});d2=PortfolioIntelligenceService.decision(bad,h2);assert d2.action==PositionAction.CLOSE;assert h2.alerts
 print('Milestone 57 Portfolio Intelligence assertions passed.')
if __name__=='__main__':main()
