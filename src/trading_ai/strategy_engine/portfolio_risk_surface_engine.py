from collections import defaultdict
from math import isfinite

from trading_ai.strategy_engine.risk_surface_policy import RiskSurfacePolicy
from trading_ai.strategy_engine.risk_surface_profile import (
    PortfolioRiskSurfaceContribution, PortfolioRiskSurfaceProfile,
    RiskAttribution, RiskSurfacePoint,
)


class PortfolioRiskSurfaceEngine:
    """Allocation-aware aggregation and attribution of compatible position surfaces."""
    def __init__(self, policy=None):
        self.policy = policy or RiskSurfacePolicy()
        self.policy.validate()

    def analyze(self, profiles, initial_capital, allocations=None, position_metadata=None):
        valid=[p for p in (profiles or []) if getattr(p,"valid",False)]
        capital=float(initial_capital or 0.0)
        if not valid or capital <= 0:
            return PortfolioRiskSurfaceProfile(initial_capital=capital,position_count=len(valid),point_count=0,worst_case_pnl=0.0,best_case_pnl=0.0,maximum_loss_pct_of_capital=0.0,surface_score=0.0,surface_grade="F",risk_severity="UNKNOWN",largest_loss_contributor="",allowed=False,valid=False,rejection_reasons=["NO_VALID_RISK_SURFACE_PROFILES"])
        allocation_values=self._allocations(valid, allocations)
        metadata_values=self._metadata(valid, position_metadata)
        maps=[]; common=None
        for profile in valid:
            point_map={(float(p.price_shock_pct),float(p.volatility_shock),int(p.time_offset_days)):p for p in profile.points}
            maps.append(point_map); common=set(point_map) if common is None else common & set(point_map)
        if not common:
            return PortfolioRiskSurfaceProfile(initial_capital=capital,position_count=len(valid),point_count=0,worst_case_pnl=0.0,best_case_pnl=0.0,maximum_loss_pct_of_capital=0.0,surface_score=0.0,surface_grade="F",risk_severity="UNKNOWN",largest_loss_contributor="",allowed=False,valid=False,rejection_reasons=["NO_COMMON_RISK_SURFACE_GRID"])
        aggregate=[]
        for key in sorted(common):
            components={name:0.0 for name in ("approximated_pnl","delta_component","gamma_component","vega_component","theta_component","rho_component")}
            for idx,mapping in enumerate(maps):
                point=mapping[key]; scale=allocation_values[idx]
                for name in components: components[name]+=float(getattr(point,name,0.0))*scale
            aggregate.append(RiskSurfacePoint(price_shock_pct=key[0],volatility_shock=key[1],time_offset_days=key[2],shocked_underlying_price=0.0,shocked_implied_volatility=0.0,**components))
        worst=min(aggregate,key=lambda p:p.approximated_pnl); best=max(aggregate,key=lambda p:p.approximated_pnl)
        base=min(aggregate,key=lambda p:(abs(p.price_shock_pct)+abs(p.volatility_shock)+abs(p.time_offset_days),abs(p.approximated_pnl)))
        portfolio_loss=abs(min(worst.approximated_pnl,0.0)); loss_pct=portfolio_loss/capital
        allocated=[max(0.0,float(getattr(p,"capital_required",0.0)))*allocation_values[i] for i,p in enumerate(valid)]
        total_allocated=sum(allocated); capital_weights=[v/total_allocated if total_allocated else 1/len(valid) for v in allocated]
        standalone_losses=[abs(min(float(getattr(p,"worst_case_pnl",0.0))*allocation_values[i],0.0)) for i,p in enumerate(valid)]
        standalone_total=sum(standalone_losses); diversification=(standalone_total-portfolio_loss)/standalone_total if standalone_total else 0.0
        worst_key=(worst.price_shock_pct,worst.volatility_shock,worst.time_offset_days)
        point_losses=[]
        for idx,mapping in enumerate(maps): point_losses.append(float(mapping[worst_key].approximated_pnl)*allocation_values[idx])
        adverse=[abs(min(v,0.0)) for v in point_losses]; adverse_total=sum(adverse)
        loss_weights=[v/adverse_total if adverse_total else 0.0 for v in adverse]
        loss_hhi=sum(v*v for v in loss_weights); capital_hhi=sum(v*v for v in capital_weights)
        contributions=[]
        for i,p in enumerate(valid):
            meta=metadata_values[i]
            contributions.append(PortfolioRiskSurfaceContribution(position_id=str(meta.get("position_id") or f"{p.symbol}:{i+1}"),symbol=str(getattr(p,"symbol","")),strategy=str(meta.get("strategy") or getattr(p,"strategy","")),sector=str(meta.get("sector") or "UNKNOWN"),correlation_group=str(meta.get("correlation_group") or ""),allocation_multiplier=allocation_values[i],capital_required=allocated[i],standalone_worst_case_pnl=-standalone_losses[i],portfolio_worst_point_pnl=point_losses[i],loss_contribution_pct=loss_weights[i],capital_weight_pct=capital_weights[i],surface_score=float(getattr(p,"surface_score",0.0)),risk_severity=str(getattr(p,"risk_severity","UNKNOWN"))))
        largest=max(contributions,key=lambda c:c.loss_contribution_pct)
        weighted_score=sum(float(getattr(p,"surface_score",0.0))*capital_weights[i] for i,p in enumerate(valid))
        concentration_penalty=max(loss_hhi-self.policy.maximum_loss_concentration_score,0.0)*50.0
        score=max(0.0,min(100.0,weighted_score-concentration_penalty))
        severity="CRITICAL" if loss_pct>=self.policy.critical_portfolio_loss_pct_of_capital else "SEVERE" if loss_pct>=self.policy.severe_portfolio_loss_pct_of_capital else "MODERATE" if loss_pct>=self.policy.maximum_portfolio_loss_pct_of_capital else "LOW"
        grade="A" if score>=90 else "B" if score>=80 else "C" if score>=70 else "D" if score>=60 else "F"
        warnings=[]; rejections=[]
        exposure_pct=total_allocated/capital
        if exposure_pct>self.policy.maximum_portfolio_exposure_pct: warnings.append("PORTFOLIO_SURFACE_EXPOSURE_ABOVE_LIMIT")
        if largest.loss_contribution_pct>self.policy.maximum_loss_contribution_pct: warnings.append("PORTFOLIO_SURFACE_LOSS_CONCENTRATION")
        if max(capital_weights)>self.policy.maximum_capital_weight_pct: warnings.append("PORTFOLIO_SURFACE_CAPITAL_CONCENTRATION")
        if diversification<self.policy.minimum_diversification_benefit: warnings.append("PORTFOLIO_SURFACE_DIVERSIFICATION_BELOW_MINIMUM")
        if severity=="CRITICAL" and self.policy.reject_critical_portfolio_risk: rejections.append("CRITICAL_PORTFOLIO_RISK_SURFACE_LOSS")
        if self.policy.reject_portfolio_concentration and "PORTFOLIO_SURFACE_LOSS_CONCENTRATION" in warnings: rejections.append("PORTFOLIO_RISK_SURFACE_CONCENTRATION_REJECTED")
        factor_values={"DELTA":worst.delta_component,"GAMMA":worst.gamma_component,"VEGA":worst.vega_component,"THETA":worst.theta_component,"RHO":worst.rho_component}
        denominator=sum(abs(v) for v in factor_values.values()) or 1.0
        factors=[RiskAttribution(factor=k,pnl=v,contribution_pct=abs(v)/denominator,adverse=v<0) for k,v in factor_values.items()]
        return PortfolioRiskSurfaceProfile(initial_capital=capital,position_count=len(valid),point_count=len(aggregate),worst_case_pnl=worst.approximated_pnl,best_case_pnl=best.approximated_pnl,base_case_pnl=base.approximated_pnl,maximum_loss_pct_of_capital=loss_pct,surface_score=score,surface_grade=grade,risk_severity=severity,largest_loss_contributor=largest.symbol,allowed=not rejections,valid=True,aggregate_points=aggregate,position_contributions=contributions,rejection_reasons=rejections,warnings=warnings,total_allocated_capital=total_allocated,portfolio_exposure_pct=exposure_pct,standalone_worst_case_loss=standalone_total,diversification_benefit=diversification,loss_concentration_score=loss_hhi,capital_concentration_score=capital_hhi,effective_position_count=(1.0/capital_hhi if capital_hhi else 0.0),largest_loss_contribution_pct=largest.loss_contribution_pct,largest_capital_weight_pct=max(capital_weights),worst_price_shock_pct=worst.price_shock_pct,worst_volatility_shock=worst.volatility_shock,worst_time_offset_days=worst.time_offset_days,factor_attributions=factors,sector_contributions=self._groups(contributions,"sector"),strategy_contributions=self._groups(contributions,"strategy"),correlation_group_contributions=self._groups(contributions,"correlation_group"),metadata={"common_grid_point_count":len(common),"input_profile_count":len(profiles or []),"allocation_aware":allocations is not None})

    def _allocations(self, profiles, allocations):
        if allocations is None: return [1.0]*len(profiles)
        if isinstance(allocations,dict): return [max(0.0,float(allocations.get(getattr(p,"symbol",""),allocations.get(i,1.0)))) for i,p in enumerate(profiles)]
        values=list(allocations)
        return [max(0.0,float(values[i] if i<len(values) else 1.0)) for i in range(len(profiles))]

    def _metadata(self, profiles, metadata):
        if metadata is None: return [{} for _ in profiles]
        if isinstance(metadata,dict): return [dict(metadata.get(getattr(p,"symbol",""),metadata.get(i,{})) or {}) for i,p in enumerate(profiles)]
        values=list(metadata); return [dict(values[i] or {}) if i<len(values) else {} for i in range(len(profiles))]

    def _groups(self, contributions, field):
        groups=defaultdict(lambda:{"pnl":0.0,"capital":0.0,"loss_contribution_pct":0.0,"positions":0})
        for item in contributions:
            key=str(getattr(item,field,"UNKNOWN") or "UNKNOWN"); row=groups[key]
            row["pnl"]+=item.portfolio_worst_point_pnl; row["capital"]+=item.capital_required; row["loss_contribution_pct"]+=item.loss_contribution_pct; row["positions"]+=1
        return [{field:key,**values} for key,values in sorted(groups.items())]
