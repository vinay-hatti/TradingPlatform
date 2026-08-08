from .profile import *
class StockOpportunityScoringEngine:
    def score(self,p:StockIntelligenceProfile,freshness=100):
        bull={'STRONG_BULLISH':95,'BULLISH':80,'WEAK_BULLISH':62,'NEUTRAL':50,'WEAK_BEARISH':35,'BEARISH':20,'STRONG_BEARISH':5}.get(p.direction,50); bear=100-bull
        part=p.participation.score if p.participation else 50; br=p.breakout.confirmation if p.breakout else 0; ctx=p.context.score if p.context else 50; align=p.alignment_score
        structure=p.structure; weights={'direction':.25,'alignment':.2,'participation':.15,'breakout':.15,'context':.15,'levels':.1}
        if structure in ('SIDEWAYS','COMPRESSION'):weights={'direction':.12,'alignment':.13,'participation':.16,'breakout':.12,'context':.12,'levels':.35}
        level_score=min(100,45+5*len(p.support_levels[:3])+5*len(p.resistance_levels[:3])+5*len(p.demand_zones[:2])+5*len(p.supply_zones[:2]))
        overall=bull*weights['direction']+align*weights['alignment']+part*weights['participation']+br*weights['breakout']+ctx*weights['context']+level_score*weights['levels']; overall*=freshness/100
        bstate=p.breakout.state if p.breakout else 'NONE'; accumulation=part if p.participation and 'ACCUMULATION' in p.participation.state else max(0,part-15); distribution=100-part if p.participation and 'DISTRIBUTION' in p.participation.state else max(0,85-part)
        scores=OpportunityScores(round(bull,2),round(bear,2),round(br if 'BREAKOUT' in bstate else br*.4,2),round(br if 'BREAKDOWN' in bstate else br*.4,2),round(accumulation,2),round(distribution,2),round((100-bull)*.4+level_score*.6,2),round((100-bear)*.4+level_score*.6,2),round(max(bull,bear)*.6+align*.4,2),round(p.breakout.failure_probability if p.breakout and 'FAILED' in bstate else max(0,50-align/2),2),round(min(100,overall*.65+p.confidence*.35),2),round(overall,2),round(min(p.confidence,freshness),2),freshness,weights=weights)
        cats={'BULLISH':scores.bullish,'BEARISH':scores.bearish,'BREAKOUT':scores.breakout,'BREAKDOWN':scores.breakdown,'ACCUMULATION':scores.accumulation,'DISTRIBUTION':scores.distribution,'REVERSAL':scores.reversal}; scores.primary_category=max(cats,key=cats.get); return scores
class StockOpportunityRankingService:
    def rank(self,profiles,category=None):
        key=(lambda p:getattr(p.scores,category.lower(),0)) if category else (lambda p:p.scores.overall if p.scores else 0)
        return sorted(profiles,key=lambda p:(key(p),p.scores.confidence if p.scores else 0,p.scores.options_suitability if p.scores else 0,p.symbol),reverse=True)
