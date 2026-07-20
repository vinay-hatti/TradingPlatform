from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence
from trading_ai.strategy_engine.decision_request import DecisionRequest
from .market_scanner_profile import MarketCandidateProfile

@dataclass(frozen=True)
class InstitutionalDecisionInputBundle:
    price_history_by_symbol: Mapping[str, Any]
    option_chain_by_symbol: Mapping[str, Any]
    sector_by_symbol: Mapping[str, str] = field(default_factory=dict)
    industry_by_symbol: Mapping[str, str] = field(default_factory=dict)
    correlation_group_by_symbol: Mapping[str, str] = field(default_factory=dict)
    portfolio_fit_by_symbol: Mapping[str, float] = field(default_factory=dict)

class InstitutionalDecisionRequestFactory:
    @staticmethod
    def _technical_score(c:MarketCandidateProfile)->float:
        vals=(float(c.trend_score),float(c.momentum_score),float(c.liquidity_score),float(c.volatility_score),float(c.regime_score)); return round(sum(vals)/len(vals),6)
    def build(self,*,candidates:Sequence[MarketCandidateProfile],inputs:InstitutionalDecisionInputBundle,target_dte:int=30,initial_capital:float=100000.0,construct_portfolio:bool=False,include_rejected:bool=True)->DecisionRequest:
        symbols=tuple(dict.fromkeys(c.symbol.upper() for c in candidates)); by={c.symbol.upper():c for c in candidates}
        return DecisionRequest(symbols=list(symbols),price_history_by_symbol={s:inputs.price_history_by_symbol.get(s) for s in symbols},option_chain_by_symbol={s:inputs.option_chain_by_symbol.get(s) for s in symbols},signal_by_symbol={s:by[s].signal for s in symbols},market_regime_by_symbol={s:by[s].regime for s in symbols},technical_score_by_symbol={s:self._technical_score(by[s]) for s in symbols},underlying_price_by_symbol={s:float(by[s].price) for s in symbols},atr_by_symbol={s:float(by[s].price)*(float(by[s].atr_pct)/100.0) for s in symbols},sector_by_symbol={s:inputs.sector_by_symbol.get(s,'UNKNOWN') for s in symbols},industry_by_symbol={s:inputs.industry_by_symbol.get(s,'UNKNOWN') for s in symbols},correlation_group_by_symbol={s:inputs.correlation_group_by_symbol.get(s,s) for s in symbols},portfolio_fit_by_symbol={s:float(inputs.portfolio_fit_by_symbol.get(s,by[s].liquidity_score)) for s in symbols},strategy_limit_per_symbol=1,expiration_limit_per_strategy=1,strike_limit_per_expiration=1,target_dte=target_dte,initial_capital=initial_capital,construct_portfolio=construct_portfolio,include_rejected=include_rejected,metadata={'source':'M34_RESEARCH_WORKSTATION_SCANNER','candidate_count':len(candidates)})
