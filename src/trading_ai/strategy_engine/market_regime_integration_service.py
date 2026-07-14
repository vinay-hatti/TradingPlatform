from trading_ai.strategy_engine.market_regime_integration_policy import MarketRegimeIntegrationPolicy
from trading_ai.strategy_engine.market_regime_integration_profile import MarketRegimeIntegrationProfile

class MarketRegimeIntegrationService:
    BULLISH={"STRONG_BULL_TREND","BULL_TREND","RECOVERY"}
    BEARISH={"STRONG_BEAR_TREND","BEAR_TREND","STRESS"}
    def __init__(self, policy=None):
        self.policy=policy or MarketRegimeIntegrationPolicy(); self.policy.validate()
    @staticmethod
    def _v(obj,name,default=None): return obj.get(name,default) if isinstance(obj,dict) else getattr(obj,name,default)
    @staticmethod
    def _clip(v,lo,hi): return max(lo,min(hi,float(v)))
    def integrate(self, *, symbol, direction, strategy, strategy_score, ranking_score, regime_profile=None, forecast_profile=None, breadth_profile=None):
        p=MarketRegimeIntegrationProfile(symbol=symbol, regime_profile=regime_profile, forecast_profile=forecast_profile, breadth_profile=breadth_profile)
        if not self.policy.enabled:
            p.valid=True; p.current_regime="DISABLED"; p.adapted_strategy_score=float(strategy_score); p.adapted_ranking_score=float(ranking_score); p.grade="N/A"; p.severity="LOW"; return p
        current=str(self._v(regime_profile,"current_regime", self._v(regime_profile,"regime","UNKNOWN")) or "UNKNOWN").upper()
        forecast=str(self._v(forecast_profile,"forecast_regime",current) or current).upper()
        portfolio=str(self._v(breadth_profile,"portfolio_regime","UNKNOWN") or "UNKNOWN").upper()
        p.current_regime=current; p.forecast_regime=forecast; p.portfolio_regime=portfolio
        p.regime_score=float(self._v(regime_profile,"regime_score",0.0) or 0.0); p.forecast_score=float(self._v(forecast_profile,"forecast_score",0.0) or 0.0); p.breadth_score=float(self._v(breadth_profile,"breadth_score",0.0) or 0.0)
        p.transition_risk=float(self._v(forecast_profile,"transition_probability",0.0) or 0.0)
        p.valid=bool(self._v(regime_profile,"valid",False))
        bullish=str(direction).upper() in {"CALL","BULLISH","LONG"}
        aligned=(bullish and current in self.BULLISH) or ((not bullish) and current in self.BEARISH)
        opposed=(bullish and current in self.BEARISH) or ((not bullish) and current in self.BULLISH)
        adj=0.0
        if aligned: adj += self.policy.aligned_strategy_bonus; p.strategy_alignment="ALIGNED"
        elif opposed: adj -= self.policy.aligned_strategy_bonus; p.strategy_alignment="OPPOSED"
        if current=="STRESS": adj -= self.policy.stress_penalty
        if current=="TRANSITION" or p.transition_risk >= 0.50: adj -= self.policy.transition_penalty; p.warnings.append("ELEVATED_REGIME_TRANSITION_RISK")
        if not self.policy.strategy_adaptation_enabled: adj=0.0
        p.strategy_score_adjustment=self._clip(adj,-self.policy.maximum_strategy_score_adjustment,self.policy.maximum_strategy_score_adjustment)
        p.ranking_score_adjustment=self._clip(p.strategy_score_adjustment*0.75,-self.policy.maximum_ranking_score_adjustment,self.policy.maximum_ranking_score_adjustment)
        p.adapted_strategy_score=self._clip(float(strategy_score)+p.strategy_score_adjustment,0,100)
        p.adapted_ranking_score=self._clip(float(ranking_score)+p.ranking_score_adjustment,0,100)
        scores=[x for x in (p.regime_score,p.forecast_score,p.breadth_score) if x>0]; p.confidence_score=sum(scores)/len(scores) if scores else 0.0
        if not p.valid: p.warnings.append("MARKET_REGIME_PROFILE_UNAVAILABLE")
        if p.regime_score and p.regime_score < self.policy.minimum_regime_score: p.warnings.append("LOW_MARKET_REGIME_SCORE")
        if p.forecast_score and p.forecast_score < self.policy.minimum_forecast_score: p.warnings.append("LOW_MARKET_REGIME_FORECAST_SCORE")
        if p.breadth_score and p.breadth_score < self.policy.minimum_breadth_score: p.warnings.append("LOW_MARKET_BREADTH_SCORE")
        sev=str(self._v(regime_profile,"risk_severity",self._v(regime_profile,"severity","LOW")) or "LOW").upper(); p.severity=sev
        if current=="STRESS" and sev=="CRITICAL" and self.policy.reject_critical_regime: p.allowed=False; p.rejection_reasons.append("CRITICAL_MARKET_REGIME")
        if self.policy.require_valid_regime and not p.valid: p.allowed=False; p.rejection_reasons.append("VALID_MARKET_REGIME_REQUIRED")
        s=p.confidence_score; p.grade="A" if s>=85 else "B" if s>=75 else "C" if s>=65 else "D" if s>=50 else "F"
        p.metadata={"strategy":strategy,"direction":direction,"raw_strategy_score":float(strategy_score),"raw_ranking_score":float(ranking_score)}
        return p
