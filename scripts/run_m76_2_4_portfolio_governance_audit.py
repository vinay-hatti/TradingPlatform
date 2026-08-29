from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from sqlalchemy import select

from trading_ai.database.session import SessionLocal
from trading_ai.institutional_options.models import InstitutionalDecisionSnapshotModel, InstitutionalOpportunityModel
from trading_ai.institutional_options.publication_scope import latest_stock_scanner_run_id
from trading_ai.portfolio_risk_allocation.models import (
    PortfolioDecisionIntelligenceModel,
    PortfolioIntelligencePublicationModel,
    PortfolioRiskSnapshotModel,
)

VERSION = "M64.2.4-SET-BASED-AUTHORITATIVE-PORTFOLIO-DECISION-AUDIT-1.0"


def _num(value, default=0.0):
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def audit(portfolio_id: str) -> dict:
    with SessionLocal() as session:
        latest_observed_risk = session.scalar(
            select(PortfolioRiskSnapshotModel)
            .where(PortfolioRiskSnapshotModel.portfolio_id == portfolio_id)
            .order_by(PortfolioRiskSnapshotModel.snapshot_timestamp.desc())
            .limit(1)
        )
        publication = session.scalar(select(PortfolioIntelligencePublicationModel).where(
            PortfolioIntelligencePublicationModel.portfolio_id == portfolio_id,
            PortfolioIntelligencePublicationModel.publication_name == "current_portfolio_allocation",
        ))
        publication_payload = dict(publication.payload_json or {}) if publication else {}
        risk = None if publication is None else session.scalar(select(PortfolioRiskSnapshotModel).where(
            PortfolioRiskSnapshotModel.portfolio_id == portfolio_id,
            PortfolioRiskSnapshotModel.snapshot_id == publication.risk_snapshot_id,
        ))
        risk_payload = dict(getattr(risk, "payload_json", {}) or {}) if risk else {}
        capital = dict(risk_payload.get("capital") or {})
        risk_summary = {
            "present": risk is not None,
            "snapshot_id": getattr(risk, "snapshot_id", None),
            "snapshot_timestamp": getattr(risk, "snapshot_timestamp", None),
            "status": getattr(risk, "status", None),
            "net_liquidation": _num(getattr(risk, "net_liquidation", None) if risk else capital.get("net_liquidation")),
            "buying_power": _num(getattr(risk, "buying_power", None) if risk else capital.get("buying_power")),
            "portfolio_heat_pct": _num(getattr(risk, "portfolio_heat_pct", None) if risk else capital.get("portfolio_heat_pct")),
            "open_risk": _num(getattr(risk, "open_risk", None) if risk else capital.get("open_risk")),
            "gross_leg_open_risk": _num(capital.get("gross_leg_open_risk")),
            "trading_risk_basis": capital.get("trading_risk_basis"),
            "heat_risk_decomposition": capital.get("heat_risk_decomposition"),
            "operational_risk": capital.get("operational_risk"),
            "position_count": int(risk_payload.get("position_count") or 0),
            "warnings": list(risk_payload.get("warnings") or []),
        }
        risk_summary["input_integrity"] = "READY" if risk_summary["net_liquidation"] > 0 and risk_summary["buying_power"] > 0 else "INPUT_INTEGRITY_BLOCK"
        current_run_id = latest_stock_scanner_run_id(session)
        opp_query = select(InstitutionalOpportunityModel, InstitutionalDecisionSnapshotModel).join(
            InstitutionalDecisionSnapshotModel,
            InstitutionalDecisionSnapshotModel.opportunity_id == InstitutionalOpportunityModel.opportunity_id,
        ).where(InstitutionalOpportunityModel.state == "READY_FOR_EXECUTION")
        if current_run_id is not None:
            opp_query = opp_query.where(InstitutionalOpportunityModel.stock_scanner_run_id == current_run_id)
        rows = list(session.execute(opp_query.order_by(InstitutionalOpportunityModel.symbol)).all())

        current_di = {}
        if risk is not None:
            di_rows = list(session.scalars(select(PortfolioDecisionIntelligenceModel).where(
                PortfolioDecisionIntelligenceModel.portfolio_id == portfolio_id,
                PortfolioDecisionIntelligenceModel.risk_snapshot_id == risk.snapshot_id,
            )).all())
            current_di = {
                row.opportunity_id: row
                for row in di_rows
                if (row.payload_json or {}).get("lifecycle", {}).get("status") == "CURRENT"
                and (row.payload_json or {}).get("lifecycle", {}).get("source_stock_scanner_run_id") == current_run_id
            }

        decision_counts = Counter()
        reason_counts = Counter()
        input_status_counts = Counter()
        rule_fail_counts = Counter()
        details = []
        for opportunity, decision_row in rows:
            di_row = current_di.get(opportunity.opportunity_id)
            if di_row is not None:
                pd = dict(di_row.payload_json or {})
                source = "CURRENT_M64_DECISION"
            else:
                decision_payload = dict(decision_row.payload_json or {})
                embedded = dict(decision_payload.get("portfolio_decision") or {})
                embedded_lifecycle = dict(embedded.get("lifecycle") or {})
                pd = embedded if (
                    embedded.get("decision_identity", {}).get("risk_snapshot_id") == risk_summary["snapshot_id"]
                    and embedded_lifecycle.get("status") == "CURRENT"
                    and embedded_lifecycle.get("source_stock_scanner_run_id") == current_run_id
                ) else {}
                source = "CURRENT_EMBEDDED_DECISION" if pd else "MISSING_CURRENT_DECISION"
            gov = dict(pd.get("decision_governance") or {})
            fit = dict(pd.get("portfolio_fit_assessment") or {})
            integrity = dict(gov.get("fit_input_integrity") or fit.get("input_integrity") or {})
            decision = str(pd.get("decision") or "MISSING").upper()
            decision_counts[decision] += 1
            status = str(gov.get("input_integrity_status") or integrity.get("status") or ("MISSING_CURRENT_DECISION" if not pd else "LEGACY_NO_DIAGNOSTICS"))
            input_status_counts[status] += 1
            reasons = list(gov.get("blocking_reasons") or []) + list(gov.get("review_reasons") or [])
            if not reasons:
                reasons = list((pd.get("explainability") or {}).get("decision_reason_codes") or [])
            if not reasons and decision == "REJECT":
                reasons = ["REJECT_WITHOUT_CURRENT_REASON_CODE"]
            if decision == "MISSING":
                reasons = ["MISSING_CURRENT_PORTFOLIO_DECISION"]
            reason_counts.update(reasons)
            failed_rules = [r for r in (gov.get("fit_rule_evaluations") or fit.get("rule_evaluations") or []) if r.get("passed") is False]
            rule_fail_counts.update(str(r.get("rule_id") or r.get("label") or "UNKNOWN_RULE") for r in failed_rules)
            impact = dict(pd.get("portfolio_impact") or {})
            before = dict(impact.get("before") or {})
            after = dict(impact.get("after") or {})
            details.append({
                "symbol": opportunity.symbol,
                "opportunity_id": opportunity.opportunity_id,
                "stock_scanner_run_id": opportunity.stock_scanner_run_id,
                "decision_source": source,
                "decision": decision,
                "portfolio_rank": (pd.get("ranking") or {}).get("rank"),
                "candidate_count": (pd.get("ranking") or {}).get("candidate_count"),
                "portfolio_fit_score": (pd.get("scores") or {}).get("portfolio_fit_score"),
                "final_portfolio_score": (pd.get("scores") or {}).get("final_portfolio_score"),
                "recommended_quantity": (pd.get("capital_allocation") or {}).get("recommended_quantity"),
                "input_integrity_status": status,
                "net_liquidation_input": integrity.get("net_liquidation"),
                "buying_power_input": integrity.get("buying_power"),
                "current_portfolio_heat_pct": before.get("portfolio_heat_pct"),
                "incremental_portfolio_heat_pct": impact.get("marginal_heat_pct"),
                "projected_portfolio_heat_pct": after.get("portfolio_heat_pct"),
                "remaining_portfolio_heat_capacity_pct": max(0.0, 20.0 - _num(after.get("portfolio_heat_pct"))) if after else None,
                "blocking_reasons": reasons,
                "failed_rules": failed_rules,
            })

        rejected = [x for x in details if x["decision"] == "REJECT"]
        missing = [x for x in details if x["decision"] == "MISSING"]
        publication_matches_current_run = bool(
            publication
            and risk
            and publication_payload.get("stock_scanner_run_id") == current_run_id
        )
        authority_has_complete_coverage = bool(
            details
            and not missing
            and len(current_di) == len(details)
        )
        authority_status = (
            "CURRENT"
            if publication_matches_current_run and authority_has_complete_coverage
            else "STALE"
            if publication
            else "MISSING"
        )
        return {
            "version": VERSION,
            "portfolio_id": portfolio_id,
            "stock_scanner_run_id": current_run_id,
            "decision_authority": {
                "status": authority_status,
                "publication_id": None if publication is None else publication.publication_id,
                "published_at": None if publication is None else publication.published_at,
                "publication_stock_scanner_run_id": publication_payload.get("stock_scanner_run_id"),
                "authoritative_risk_snapshot_id": None if risk is None else risk.snapshot_id,
                "latest_observed_risk_snapshot_id": None if latest_observed_risk is None else latest_observed_risk.snapshot_id,
                "newer_unpublished_risk_observation_present": bool(
                    risk and latest_observed_risk and risk.snapshot_id != latest_observed_risk.snapshot_id
                ),
            },
            "risk_snapshot": risk_summary,
            "current_ready_for_execution_candidates": len(details),
            "current_portfolio_decisions": len(current_di),
            "missing_current_decisions": len(missing),
            "decision_distribution": dict(decision_counts),
            "input_integrity_distribution": dict(input_status_counts),
            "rejection_reason_distribution": dict(reason_counts.most_common()),
            "failed_rule_distribution": dict(rule_fail_counts.most_common()),
            "rejected_count": len(rejected),
            "rejected_pct": round(len(rejected) / len(details) * 100, 2) if details else 0.0,
            "diagnosis": {
                "all_current_candidates_have_current_decisions": len(missing) == 0,
                "publication_matches_current_stock_run": publication_matches_current_run,
                "publication_has_complete_current_decision_coverage": authority_has_complete_coverage,
                "all_or_most_rejected": len(details) > 0 and len(rejected) / len(details) >= 0.75,
                "risk_snapshot_capital_inputs_valid": risk_summary["input_integrity"] == "READY",
                "dominant_rejection_reason": reason_counts.most_common(1)[0][0] if reason_counts else None,
                "dominant_rejection_count": reason_counts.most_common(1)[0][1] if reason_counts else 0,
            },
            "details": details,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only current-run portfolio-governance audit")
    parser.add_argument("--portfolio-id", default="PAPER-PRIMARY")
    parser.add_argument("--output")
    args = parser.parse_args()
    report = audit(args.portfolio_id)
    text = json.dumps(report, indent=2, default=str)
    print(text)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n")


if __name__ == "__main__":
    main()
