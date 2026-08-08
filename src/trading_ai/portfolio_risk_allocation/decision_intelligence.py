from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from math import sqrt
from uuid import uuid4

from sqlalchemy import MetaData, Table, func, inspect, select

from trading_ai.institutional_options.models import (
    InstitutionalDecisionSnapshotModel,
    InstitutionalOpportunityModel,
)
from .models import (
    PortfolioCorrelationSnapshotModel,
    PortfolioDecisionIntelligenceModel,
)
from .service import PortfolioRiskAllocationService, clamp, number


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class InstitutionalDecisionIntelligenceService:
    """Canonical portfolio-aware decision layer for M64 and future intelligence modules."""

    POLICY_VERSION = "M64-DECISION-INTELLIGENCE-1.0"

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.risk_service = PortfolioRiskAllocationService(session_factory)

    def build(self, portfolio_id: str = "PAPER-PRIMARY", opportunity_ids: list[str] | None = None, limit: int | None = None):
        risk = self.risk_service.current(portfolio_id) or self.risk_service.build(portfolio_id)
        with self.session_factory() as session:
            query = select(InstitutionalDecisionSnapshotModel).join(
                InstitutionalOpportunityModel,
                InstitutionalOpportunityModel.opportunity_id == InstitutionalDecisionSnapshotModel.opportunity_id,
            ).where(InstitutionalOpportunityModel.state == "READY_FOR_EXECUTION")
            if opportunity_ids:
                query = query.where(InstitutionalDecisionSnapshotModel.opportunity_id.in_(opportunity_ids))
            query = query.order_by(InstitutionalDecisionSnapshotModel.institutional_score.desc())
            if limit:
                query = query.limit(limit)
            rows = list(session.scalars(query).all())
            symbols = [str((row.payload_json or {}).get("symbol") or "").upper() for row in rows]
            correlation = self._correlation_snapshot(session, portfolio_id, risk, symbols)
            assessments = []
            for row in rows:
                payload = dict(row.payload_json or {})
                symbol = str(payload.get("symbol") or payload.get("underlying", {}).get("symbol") or "UNKNOWN").upper()
                sector = str(payload.get("sector") or payload.get("underlying", {}).get("sector_context", {}).get("sector") or "UNKNOWN")
                capital = number(row.capital_required or payload.get("valuation", {}).get("capital", {}).get("capital_required"))
                expected_value = number(row.expected_value or payload.get("valuation", {}).get("expected_value"))
                probability = number(row.calibrated_probability or payload.get("valuation", {}).get("probability", {}).get("calibrated_probability"), .5)
                selected_contract = payload.get("selected_contract") or {}
                greeks = self._candidate_greeks(selected_contract)
                candidate = {
                    "candidate_id": row.opportunity_id,
                    "opportunity_id": row.opportunity_id,
                    "symbol": symbol,
                    "sector": sector,
                    "strategy": row.selected_strategy,
                    "capital_required": capital,
                    "maximum_loss": capital,
                    "unit_risk": max(capital, 1.0),
                    "expected_value": expected_value,
                    "probability": probability,
                }
                fit = self.risk_service.assess(candidate, portfolio_id)
                corr = self._portfolio_correlation(symbol, correlation)
                marginal = self._marginal_impact(risk, capital, greeks, corr)
                capital_efficiency = clamp((expected_value / capital * 100) if capital else 0)
                diversification_benefit = clamp(100 - abs(corr) * 100)
                opportunity_pre_score = clamp(
                    .45 * number(row.institutional_score)
                    + .30 * fit["portfolio_fit_score"]
                    + .15 * capital_efficiency
                    + .10 * diversification_benefit
                )
                assessments.append({
                    "row": row, "payload": payload, "symbol": symbol, "sector": sector,
                    "fit": fit, "correlation": corr, "marginal": marginal,
                    "capital_efficiency": capital_efficiency,
                    "diversification_benefit": diversification_benefit,
                    "pre_score": opportunity_pre_score,
                })
            ordered = sorted(assessments, key=lambda item: item["pre_score"], reverse=True)
            best = ordered[0]["pre_score"] if ordered else 0.0
            results = []
            for rank, item in enumerate(ordered, 1):
                row = item["row"]
                opportunity_cost = clamp(100 - max(0, best - item["pre_score"]) * 4)
                final_score = clamp(.85 * item["pre_score"] + .15 * opportunity_cost)
                decision = self._decision(final_score, item["fit"]["decision"], item["marginal"])
                explanation = self._explain(item, opportunity_cost, decision, rank)
                canonical = {
                    "policy_version": self.POLICY_VERSION,
                    "symbol": item["symbol"],
                    "sector": item["sector"],
                    "strategy": row.selected_strategy,
                    "decision_identity": {
                        "opportunity_id": row.opportunity_id,
                        "institutional_decision_snapshot_id": row.decision_snapshot_id,
                        "risk_snapshot_id": risk["snapshot_id"],
                        "portfolio_id": portfolio_id,
                    },
                    "scores": {
                        "institutional_score": number(row.institutional_score),
                        "portfolio_fit_score": item["fit"]["portfolio_fit_score"],
                        "capital_efficiency_score": item["capital_efficiency"],
                        "diversification_benefit_score": item["diversification_benefit"],
                        "opportunity_cost_score": opportunity_cost,
                        "final_portfolio_score": final_score,
                    },
                    "correlation": {"portfolio_correlation": item["correlation"], "snapshot_id": correlation["correlation_snapshot_id"]},
                    "portfolio_impact": item["marginal"],
                    "capital_allocation": {
                        "recommended_quantity": item["fit"]["recommended_quantity"],
                        "recommended_capital": item["fit"]["recommended_capital"],
                        "minimum_quantity": 1 if item["fit"]["recommended_quantity"] else 0,
                        "maximum_quantity": max(item["fit"]["recommended_quantity"], min(10, item["fit"]["recommended_quantity"] * 2)),
                        "risk_budget_snapshot_id": risk["snapshot_id"],
                    },
                    "ranking": {"rank": rank, "candidate_count": len(ordered)},
                    "decision": decision,
                    "explainability": explanation,
                    "future_extensions": {"inflection_intelligence": None, "option_valuation_intelligence": None, "learning_confidence": None},
                }
                state_hash = sha256(json.dumps(canonical, sort_keys=True, default=str).encode()).hexdigest()
                existing = session.scalar(select(PortfolioDecisionIntelligenceModel).where(
                    PortfolioDecisionIntelligenceModel.portfolio_id == portfolio_id,
                    PortfolioDecisionIntelligenceModel.opportunity_id == row.opportunity_id,
                    PortfolioDecisionIntelligenceModel.risk_snapshot_id == risk["snapshot_id"],
                ))
                if existing is None:
                    existing = PortfolioDecisionIntelligenceModel(
                        decision_intelligence_id="M64-DI-" + uuid4().hex.upper(),
                        portfolio_id=portfolio_id, opportunity_id=row.opportunity_id,
                        institutional_decision_snapshot_id=row.decision_snapshot_id,
                        risk_snapshot_id=risk["snapshot_id"], created_at=utc_now(),
                        portfolio_fit_score=item["fit"]["portfolio_fit_score"],
                        opportunity_cost_score=opportunity_cost, final_portfolio_score=final_score,
                        recommended_quantity=item["fit"]["recommended_quantity"],
                        recommended_capital=item["fit"]["recommended_capital"], decision=decision,
                        rank=rank, state_hash=state_hash, payload_json=canonical,
                    )
                    session.add(existing)
                else:
                    existing.portfolio_fit_score=item["fit"]["portfolio_fit_score"]
                    existing.opportunity_cost_score=opportunity_cost
                    existing.final_portfolio_score=final_score
                    existing.recommended_quantity=item["fit"]["recommended_quantity"]
                    existing.recommended_capital=item["fit"]["recommended_capital"]
                    existing.decision=decision; existing.rank=rank; existing.state_hash=state_hash; existing.payload_json=canonical
                base_payload = dict(row.payload_json or {})
                base_payload["portfolio_decision"] = canonical
                row.payload_json = base_payload
                results.append(canonical)
            session.commit()
            return {"portfolio_id": portfolio_id, "risk_snapshot_id": risk["snapshot_id"], "correlation_snapshot_id": correlation["correlation_snapshot_id"], "requested": len(rows), "built": len(results), "rankings": results}

    def current(self, opportunity_id: str, portfolio_id: str = "PAPER-PRIMARY"):
        with self.session_factory() as session:
            row = session.scalar(select(PortfolioDecisionIntelligenceModel).where(
                PortfolioDecisionIntelligenceModel.portfolio_id == portfolio_id,
                PortfolioDecisionIntelligenceModel.opportunity_id == opportunity_id,
            ).order_by(PortfolioDecisionIntelligenceModel.created_at.desc()).limit(1))
            return None if row is None else dict(row.payload_json or {})

    def rankings(self, portfolio_id: str = "PAPER-PRIMARY", limit: int = 100):
        with self.session_factory() as session:
            rows = list(session.scalars(select(PortfolioDecisionIntelligenceModel).where(
                PortfolioDecisionIntelligenceModel.portfolio_id == portfolio_id
            ).order_by(PortfolioDecisionIntelligenceModel.rank.asc()).limit(limit)).all())
            return [dict(row.payload_json or {}) for row in rows]

    def _candidate_greeks(self, selected_contract: dict) -> dict:
        scorecard = selected_contract.get("contract_scorecard") or selected_contract.get("scorecard") or {}
        greeks = selected_contract.get("greeks") or scorecard.get("greeks") or {}
        return {name: number(greeks.get(name)) for name in ("delta","gamma","theta","vega","rho")}

    def _marginal_impact(self, risk: dict, capital: float, greeks: dict, corr: float) -> dict:
        payload=risk["payload_json"]; net=max(number(risk["net_liquidation"]),1)
        before=payload["greeks"]; heat=number(risk["portfolio_heat_pct"]); var=number(risk["var_95"])
        quantity=max(1, int(min(net*.02, max(capital,1))/max(capital,1)))
        marginal={k:number(greeks.get(k))*100*quantity for k in ("delta","gamma","theta","vega","rho")}
        marginal_var=abs(marginal["delta"])*.012 + abs(marginal["gamma"])*.2 + abs(marginal["vega"])*.03
        return {
            "before": {"greeks": before, "var_95": var, "portfolio_heat_pct": heat, "capital_usage_pct": payload["capital"]["capital_usage_pct"]},
            "marginal_greeks": marginal,
            "marginal_var_95": marginal_var,
            "marginal_heat_pct": capital/net*100,
            "after": {"delta":number(before.get("delta"))+marginal["delta"], "gamma":number(before.get("gamma"))+marginal["gamma"], "theta":number(before.get("theta"))+marginal["theta"], "vega":number(before.get("vega"))+marginal["vega"], "var_95":var+marginal_var, "portfolio_heat_pct":heat+capital/net*100},
            "correlation_penalty": abs(corr)*100,
        }

    def _correlation_snapshot(self, session, portfolio_id: str, risk: dict, candidates: list[str]) -> dict:
        symbols=set(candidates)
        symbols.update((risk.get("payload_json") or {}).get("exposures",{}).get("symbol",{}).keys())
        symbols.discard(""); matrix={}; tables=inspect(session.get_bind()).get_table_names()
        if "price_history" in tables:
            table=Table("price_history",MetaData(),autoload_with=session.get_bind())
            series={s:self._returns(session,table,s) for s in symbols}
            for a in symbols:
                matrix[a]={}
                for b in symbols: matrix[a][b]=self._corr(series.get(a,{}),series.get(b,{}))
        payload={"policy_version":self.POLICY_VERSION,"windows":[60],"symbols":sorted(symbols),"matrix":matrix}
        row=PortfolioCorrelationSnapshotModel(correlation_snapshot_id="M64-CORR-"+uuid4().hex.upper(),portfolio_id=portfolio_id,risk_snapshot_id=risk["snapshot_id"],generated_at=utc_now(),payload_json=payload)
        session.add(row); session.flush()
        return {"correlation_snapshot_id":row.correlation_snapshot_id,**payload}

    def _returns(self, session, table, symbol):
        rows=session.execute(select(table.c.date,table.c.close).where(func.upper(table.c.symbol)==symbol.upper()).order_by(table.c.date.desc()).limit(61)).all()
        rows=list(reversed(rows)); out={}
        for i in range(1,len(rows)):
            prev=number(rows[i-1][1]); cur=number(rows[i][1])
            if prev>0: out[str(rows[i][0])]=cur/prev-1
        return out

    def _corr(self,a,b):
        keys=sorted(set(a)&set(b))
        if len(keys)<10:return 0.0
        x=[a[k] for k in keys];y=[b[k] for k in keys];mx=sum(x)/len(x);my=sum(y)/len(y)
        num=sum((u-mx)*(v-my) for u,v in zip(x,y));dx=sqrt(sum((u-mx)**2 for u in x));dy=sqrt(sum((v-my)**2 for v in y))
        return num/(dx*dy) if dx and dy else 0.0

    def _portfolio_correlation(self,symbol,corr):
        row=(corr.get("matrix") or {}).get(symbol,{})
        values=[abs(number(v)) for k,v in row.items() if k!=symbol]
        return sum(values)/len(values) if values else 0.0

    def _decision(self, score, fit_decision, marginal):
        if fit_decision=="REJECT" or score<55:return "REJECT"
        if score<72 or marginal["after"]["portfolio_heat_pct"]>20:return "REVIEW"
        return "ACCEPT"

    def _explain(self,item,opportunity_cost,decision,rank):
        positive=[]; risks=[]
        if item["fit"]["portfolio_fit_score"]>=80:positive.append("Strong portfolio fit")
        if abs(item["correlation"])<.35:positive.append("Low correlation with current portfolio")
        if item["diversification_benefit"]>=65:positive.append("Improves diversification")
        if item["capital_efficiency"]>=50:positive.append("Capital efficient expected value")
        if opportunity_cost>=85:positive.append("Competitive use of available capital")
        for reason in item["fit"].get("reasons",[]):
            if "LIMIT" in reason:risks.append(reason.replace("_"," ").title())
        if item["marginal"]["after"]["portfolio_heat_pct"]>20:risks.append("Portfolio heat would exceed policy")
        return {"summary":f"{decision}: portfolio rank {rank}","positive_reasons":positive,"risk_reasons":risks,"why_not_higher_ranked":None if rank==1 else "A higher-ranked candidate offers better expected portfolio improvement."}
