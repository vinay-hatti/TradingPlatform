from __future__ import annotations
from typing import Any, Iterable, Mapping
from trading_ai.strategy_engine.decision_request import DecisionRequest
from trading_ai.strategy_engine.institutional_decision_service import InstitutionalDecisionService
from .institutional_scanner_profile import InstitutionalScannerDecisionProfile, InstitutionalScannerRunProfile

class InstitutionalDecisionEngineAdapter:
    def __init__(self, service: InstitutionalDecisionService | None = None):
        self.service=service or InstitutionalDecisionService()
    @staticmethod
    def _value(source: Any,*names:str,default:Any=None)->Any:
        for name in names:
            if source is None: break
            value=source.get(name) if isinstance(source,Mapping) else getattr(source,name,None)
            if value is not None: return value
        return default
    @classmethod
    def _nested_value(cls,source:Any,containers:Iterable[str],names:Iterable[str],default:Any=None)->Any:
        direct=cls._value(source,*tuple(names),default=None)
        if direct is not None: return direct
        metadata=cls._value(source,'metadata',default={}) or {}
        for container_name in containers:
            container=cls._value(source,container_name,default=None)
            if container is None and isinstance(metadata,Mapping): container=metadata.get(container_name)
            value=cls._value(container,*tuple(names),default=None)
            if value is not None: return value
        return default
    @staticmethod
    def _number(value:Any,default:float=0.0)->float:
        try:return float(value)
        except (TypeError,ValueError):return default
    @classmethod
    def _probability(cls,value:Any)->float:
        n=cls._number(value); return n/100.0 if n>1.0 else n
    @staticmethod
    def _tuple(value:Any)->tuple[str,...]:
        if value is None:return ()
        if isinstance(value,str):return (value,)
        try:return tuple(str(x) for x in value)
        except TypeError:return (str(value),)
    @classmethod
    def _reward_risk(cls,d:Any)->float:
        direct=cls._number(cls._value(d,'reward_risk_ratio','risk_reward_ratio',default=0.0))
        if direct>0:return direct
        p=cls._number(cls._value(d,'expected_profit',default=0.0)); l=abs(cls._number(cls._value(d,'maximum_loss',default=0.0)))
        return p/l if l>0 else 0.0
    @classmethod
    def normalize_decision(cls,d:Any)->InstitutionalScannerDecisionProfile:
        pop=cls._probability(cls._nested_value(d,('probability_profile','probability_calibration_profile','calibration_profile'),('probability_of_profit','calibrated_probability','probability'),default=0.0))
        cal=cls._probability(cls._nested_value(d,('probability_calibration_profile','calibration_profile','probability_profile'),('calibrated_probability','calibrated_probability_of_profit','probability_of_profit'),default=pop))
        er=cls._number(cls._nested_value(d,('probability_profile','expected_value_profile'),('expected_return','expected_return_on_capital','expected_return_on_risk'),default=0.0))
        regime=cls._number(cls._nested_value(d,('market_regime_profile','market_regime_integration_profile','regime_profile'),('regime_confidence','confidence_score','confidence','score'),default=0.0))
        execution=cls._number(cls._nested_value(d,('execution_profile','execution_analytics_profile'),('execution_quality','execution_score','quality_score','score'),default=cls._value(d,'execution_score',default=0.0)))
        tail=cls._number(cls._nested_value(d,('distribution_risk_profile','tail_risk_profile'),('tail_risk_score','risk_score'),default=0.0))
        risk=tail if tail>0 else max(0.0,min(100.0,100.0-cls._number(cls._value(d,'ranking_score',default=0.0))))
        return InstitutionalScannerDecisionProfile(symbol=str(cls._value(d,'symbol',default='')).upper(),available=True,allowed=bool(cls._value(d,'allowed',default=False)),selected=bool(cls._value(d,'selected',default=False)),action=str(cls._value(d,'action',default='HOLD')),readiness=str(cls._value(d,'readiness',default='UNKNOWN')),strategy=str(cls._value(d,'strategy',default='UNAVAILABLE')),decision_confidence=cls._number(cls._value(d,'decision_confidence','confidence_score','ranking_score',default=0.0)),probability_of_profit=pop,calibrated_probability=cal,expected_return=er,expected_profit=cls._number(cls._value(d,'expected_profit',default=0.0)),maximum_loss=abs(cls._number(cls._value(d,'maximum_loss',default=0.0))),risk_score=risk,reward_risk_ratio=cls._reward_risk(d),regime_confidence=regime,execution_quality=execution,tail_risk_score=tail,tail_risk_grade=str(cls._nested_value(d,('distribution_risk_profile','tail_risk_profile'),('tail_risk_grade','risk_grade'),default='UNKNOWN')),recommended_position_size_pct=cls._number(cls._value(d,'recommended_position_size_pct','position_size_pct',default=0.0)),stop_loss_pct=cls._number(cls._value(d,'stop_loss_pct',default=0.0)),take_profit_pct=cls._number(cls._value(d,'take_profit_pct',default=0.0)),warnings=cls._tuple(cls._value(d,'warnings',default=())),rejection_reasons=cls._tuple(cls._value(d,'rejection_reasons',default=())),metadata={'decision_id':cls._value(d,'decision_id',default=None),'rank':cls._value(d,'rank',default=None),'ranking_score':cls._number(cls._value(d,'ranking_score',default=0.0)),'strategy_score':cls._number(cls._value(d,'strategy_score',default=0.0))})
    def run(self,request:DecisionRequest)->InstitutionalScannerRunProfile:
        if hasattr(self.service,'run'): result=self.service.run(request=request)
        elif hasattr(self.service,'engine'): result=self.service.engine.run(request)
        else: raise TypeError('InstitutionalDecisionService exposes neither run() nor engine.run().')
        normalized=[self.normalize_decision(x) for x in getattr(result,'decisions',())]
        by_symbol={}
        for item in normalized: by_symbol.setdefault(item.symbol,item)
        return InstitutionalScannerRunProfile(decisions_by_symbol=by_symbol,total_symbols=int(getattr(result,'total_symbols',len(by_symbol))),processed_symbols=int(getattr(result,'processed_symbols',len(by_symbol))),selected_count=int(getattr(result,'selected_count',sum(x.selected for x in by_symbol.values()))),valid=bool(getattr(result,'valid',bool(by_symbol))),overall_readiness=str(getattr(result,'overall_readiness','UNKNOWN')),overall_action=str(getattr(result,'overall_action','HOLD')),warnings=self._tuple(getattr(result,'warnings',())),errors=self._tuple(getattr(result,'errors',())),metadata=dict(getattr(result,'metadata',{}) or {}))
