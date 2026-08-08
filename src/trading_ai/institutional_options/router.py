from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc

from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from trading_ai.production_api.security import require_access, require_mutation_access

from .models import (InstitutionalOpportunityModel, OpportunityThesisModel, StrategyCandidateModel, StrategyComparisonModel)
from .opportunity_ingestion import InstitutionalOpportunityIngestionService
from .strategy_generation import InstitutionalStrategyGenerationService
from .contract_optimization import InstitutionalContractOptimizationService
from .models import ContractRecommendationModel, StrategyValuationModel, ExecutionRecommendationModel, PositionManagementSnapshotModel, InstitutionalOpportunityAuditModel, InstitutionalDecisionSnapshotModel
from .valuation import InstitutionalStrategyValuationService
from .management import InstitutionalDynamicManagementService
from .decision import InstitutionalDecisionService
from .publication_scope import latest_stock_scanner_run_id

router = APIRouter(prefix="/api/v1/institutional-options", tags=["institutional-options"])


@router.get("/handoff/trade-builder-config", response_model=ApiEnvelope)
def get_trade_builder_config(request: Request, _: str = Depends(require_access)):
    """Read current Institutional Options -> Trade Builder risk defaults from project .env."""
    from .handoff import HandoffPolicy
    from .trade_builder_config import load_trade_builder_risk_config

    try:
        config = load_trade_builder_risk_config()
        policy = HandoffPolicy()
        if config.capital < policy.minimum_capital:
            raise ValueError("Configured Trade Builder capital is below the governed minimum")
        if not 0 < config.risk_budget_pct <= policy.maximum_risk_budget_pct:
            raise ValueError("Configured Trade Builder risk budget percentage is outside governed limits")
        return envelope(request, config.as_dict())
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


def envelope(request: Request, data, **metadata):
    return ApiEnvelope(request_id=request.state.request_id, data=data, metadata=metadata)




@router.get("/workspace/opportunities", response_model=ApiEnvelope)
def list_workspace_opportunities(
    request: Request,
    state: str | None = None,
    direction: str | None = None,
    symbol: str | None = None,
    minimum_score: float | None = Query(None, ge=0, le=100),
    limit: int = Query(500, ge=1, le=5000),
    view: str = Query("current", pattern="^(current|history|all)$"),
    _: str = Depends(require_access),
):
    """Decision-workspace summaries for the parallel Institutional Options page."""
    with SessionLocal() as session:
        query = session.query(InstitutionalOpportunityModel)
        latest_run_id = latest_stock_scanner_run_id(session)
        if view == "current":
            if latest_run_id is None:
                return envelope(request, [], count=0, view=view, stock_scanner_run_id=None)
            query = query.filter(InstitutionalOpportunityModel.stock_scanner_run_id == latest_run_id)
        elif view == "history" and latest_run_id is not None:
            query = query.filter(InstitutionalOpportunityModel.stock_scanner_run_id != latest_run_id)
        if state:
            query = query.filter(InstitutionalOpportunityModel.state == state.upper())
        if direction:
            query = query.filter(InstitutionalOpportunityModel.direction == direction.upper())
        if symbol:
            query = query.filter(InstitutionalOpportunityModel.symbol.ilike(f"%{symbol.strip()}%"))
        if minimum_score is not None:
            query = query.filter(InstitutionalOpportunityModel.overall_score >= minimum_score)
        rows = query.order_by(desc(InstitutionalOpportunityModel.overall_score), desc(InstitutionalOpportunityModel.confidence), InstitutionalOpportunityModel.symbol).limit(limit).all()
        result = []
        for row in rows:
            selected = session.query(StrategyValuationModel).filter_by(opportunity_id=row.opportunity_id, selected=True).first()
            execution = session.query(ExecutionRecommendationModel).filter_by(opportunity_id=row.opportunity_id).first()
            payload = dict(row.payload_json or {}) | {"state": row.state, "version": row.version}
            if selected is not None:
                valuation = dict(selected.payload_json or {})
                payload["best_strategy"] = valuation.get("strategy")
                payload["best_strategy_score"] = selected.strategy_score
                payload["calibrated_probability"] = selected.calibrated_probability
                payload["expected_value"] = selected.expected_value
                payload["expected_return_on_risk"] = selected.expected_return_on_risk
            if execution is not None:
                execution_payload = dict(execution.payload_json or {})
                payload["ready_for_trade_builder"] = execution.ready_for_trade_builder
                payload["underlying_stop"] = execution.underlying_stop
                payload["underlying_targets"] = execution_payload.get("underlying_targets", [])
            decision = session.query(InstitutionalDecisionSnapshotModel).filter_by(opportunity_id=row.opportunity_id).first()
            if decision is not None:
                decision_payload = dict(decision.payload_json or {})
                if decision_payload.get("portfolio_decision"):
                    payload["portfolio_decision"] = decision_payload["portfolio_decision"]
            result.append(payload)
        return envelope(request, result, count=len(result), view=view, stock_scanner_run_id=latest_run_id)


@router.get("/workspace/opportunities/{opportunity_id}", response_model=ApiEnvelope)
def get_workspace_opportunity(opportunity_id: str, request: Request, _: str = Depends(require_access)):
    """Complete persisted decision workspace for one underlying-first opportunity."""
    with SessionLocal() as session:
        row = session.get(InstitutionalOpportunityModel, opportunity_id)
        if row is None:
            raise HTTPException(404, "Institutional option opportunity not found")
        thesis = session.query(OpportunityThesisModel).filter_by(opportunity_id=opportunity_id).first()
        strategies = session.query(StrategyCandidateModel).filter_by(opportunity_id=opportunity_id).order_by(StrategyCandidateModel.rank.asc().nullslast(), desc(StrategyCandidateModel.strategy_score), StrategyCandidateModel.strategy).all()
        comparison = session.query(StrategyComparisonModel).filter_by(opportunity_id=opportunity_id).first()
        contracts = session.query(ContractRecommendationModel).filter_by(opportunity_id=opportunity_id).order_by(ContractRecommendationModel.executable.desc(), desc(ContractRecommendationModel.liquidity_score)).all()
        valuations = session.query(StrategyValuationModel).filter_by(opportunity_id=opportunity_id).order_by(StrategyValuationModel.selected.desc(), desc(StrategyValuationModel.strategy_score)).all()
        execution = session.query(ExecutionRecommendationModel).filter_by(opportunity_id=opportunity_id).first()
        management = session.query(PositionManagementSnapshotModel).filter_by(opportunity_id=opportunity_id).order_by(desc(PositionManagementSnapshotModel.created_at)).all()
        decision = session.query(InstitutionalDecisionSnapshotModel).filter_by(opportunity_id=opportunity_id).first()
        audit = session.query(InstitutionalOpportunityAuditModel).filter_by(opportunity_id=opportunity_id).order_by(InstitutionalOpportunityAuditModel.event_timestamp.asc()).all()
        return envelope(request, {
            "opportunity": dict(row.payload_json or {}) | {"state": row.state, "version": row.version},
            "thesis": None if thesis is None else dict(thesis.payload_json or {}),
            "strategies": [dict(item.payload_json or {}) for item in strategies],
            "comparison": None if comparison is None else dict(comparison.payload_json or {}),
            "contracts": [dict(item.payload_json or {}) for item in contracts],
            "valuations": [dict(item.payload_json or {}) for item in valuations],
            "execution_recommendation": None if execution is None else dict(execution.payload_json or {}),
            "management_snapshots": [dict(item.payload_json or {}) for item in management],
            "decision_snapshot": None if decision is None else dict(decision.payload_json or {}),
            "audit": [dict(item.payload_json or {}) | {"previous_state": item.previous_state, "new_state": item.new_state, "actor": item.actor, "reason": item.reason, "event_timestamp": item.event_timestamp} for item in audit],
        })


@router.post("/opportunities/ingest", response_model=ApiEnvelope)
def ingest_opportunities(
    request: Request,
    publication_name: str = "current_stock_intelligence",
    symbols: str | None = None,
    limit: int | None = Query(None, ge=1, le=5000),
    _: str = Depends(require_access),
):
    parsed_symbols = None if not symbols else [item.strip().upper() for item in symbols.split(",") if item.strip()]
    with SessionLocal() as session:
        result = InstitutionalOpportunityIngestionService(session).ingest(
            publication_name=publication_name,
            symbols=parsed_symbols,
            limit=limit,
        )
        session.commit()
        return envelope(request, result.__dict__)


@router.get("/opportunities", response_model=ApiEnvelope)
def list_opportunities(
    request: Request,
    state: str | None = None,
    symbol: str | None = None,
    limit: int = Query(200, ge=1, le=2000),
    view: str = Query("current", pattern="^(current|history|all)$"),
    _: str = Depends(require_access),
):
    with SessionLocal() as session:
        query = session.query(InstitutionalOpportunityModel)
        latest_run_id = latest_stock_scanner_run_id(session)
        if view == "current":
            if latest_run_id is None:
                return envelope(request, [], count=0, view=view, stock_scanner_run_id=None)
            query = query.filter(InstitutionalOpportunityModel.stock_scanner_run_id == latest_run_id)
        elif view == "history" and latest_run_id is not None:
            query = query.filter(InstitutionalOpportunityModel.stock_scanner_run_id != latest_run_id)
        if state:
            query = query.filter(InstitutionalOpportunityModel.state == state.upper())
        if symbol:
            query = query.filter(InstitutionalOpportunityModel.symbol == symbol.upper())
        rows = query.order_by(desc(InstitutionalOpportunityModel.overall_score), InstitutionalOpportunityModel.symbol).limit(limit).all()
        return envelope(request, [dict(row.payload_json or {}) | {"state": row.state, "version": row.version} for row in rows], count=len(rows), view=view, stock_scanner_run_id=latest_run_id)


@router.get("/opportunities/{opportunity_id}", response_model=ApiEnvelope)
def get_opportunity(opportunity_id: str, request: Request, _: str = Depends(require_access)):
    with SessionLocal() as session:
        row = session.get(InstitutionalOpportunityModel, opportunity_id)
        if row is None:
            raise HTTPException(404, "Institutional option opportunity not found")
        thesis = session.query(OpportunityThesisModel).filter(OpportunityThesisModel.opportunity_id == opportunity_id).first()
        return envelope(request, {
            "opportunity": dict(row.payload_json or {}) | {"state": row.state, "version": row.version},
            "thesis": None if thesis is None else dict(thesis.payload_json or {}),
        })


@router.post("/strategies/generate", response_model=ApiEnvelope)
def generate_strategies(
    request: Request,
    opportunity_ids: str | None = None,
    limit: int | None = Query(None, ge=1, le=5000),
    _: str = Depends(require_access),
):
    parsed = None if not opportunity_ids else [item.strip() for item in opportunity_ids.split(",") if item.strip()]
    with SessionLocal() as session:
        result = InstitutionalStrategyGenerationService(session).generate(opportunity_ids=parsed, limit=limit)
        session.commit()
        return envelope(request, result.__dict__)


@router.get("/opportunities/{opportunity_id}/strategies", response_model=ApiEnvelope)
def list_opportunity_strategies(opportunity_id: str, request: Request, _: str = Depends(require_access)):
    with SessionLocal() as session:
        rows = session.query(StrategyCandidateModel).filter(
            StrategyCandidateModel.opportunity_id == opportunity_id
        ).order_by(StrategyCandidateModel.rank.asc().nullslast(), StrategyCandidateModel.strategy).all()
        comparison = session.query(StrategyComparisonModel).filter(
            StrategyComparisonModel.opportunity_id == opportunity_id
        ).first()
        return envelope(request, {
            "strategies": [dict(row.payload_json or {}) for row in rows],
            "comparison": None if comparison is None else dict(comparison.payload_json or {}),
        }, count=len(rows))


@router.post("/contracts/optimize", response_model=ApiEnvelope)
def optimize_contracts(
    request: Request,
    opportunity_ids: str | None = None,
    limit: int | None = Query(None, ge=1, le=5000),
    _: str = Depends(require_access),
):
    parsed = None if not opportunity_ids else [item.strip() for item in opportunity_ids.split(",") if item.strip()]
    with SessionLocal() as session:
        result = InstitutionalContractOptimizationService(session).optimize(opportunity_ids=parsed, limit=limit)
        session.commit()
        return envelope(request, result.__dict__)


@router.get("/opportunities/{opportunity_id}/contracts", response_model=ApiEnvelope)
def list_opportunity_contracts(opportunity_id: str, request: Request, _: str = Depends(require_access)):
    with SessionLocal() as session:
        rows = session.query(ContractRecommendationModel).filter(
            ContractRecommendationModel.opportunity_id == opportunity_id
        ).order_by(ContractRecommendationModel.executable.desc(), ContractRecommendationModel.liquidity_score.desc().nullslast()).all()
        return envelope(request, [dict(row.payload_json or {}) for row in rows], count=len(rows))


@router.post("/strategies/value", response_model=ApiEnvelope)
def value_strategies(
    request: Request,
    opportunity_ids: str | None = None,
    limit: int | None = Query(None, ge=1, le=5000),
    _: str = Depends(require_access),
):
    parsed = None if not opportunity_ids else [item.strip() for item in opportunity_ids.split(",") if item.strip()]
    with SessionLocal() as session:
        result = InstitutionalStrategyValuationService(session).value(opportunity_ids=parsed, limit=limit)
        session.commit()
        return envelope(request, result.__dict__)


@router.post("/management/generate", response_model=ApiEnvelope)
def generate_management(
    request: Request,
    opportunity_ids: str | None = None,
    limit: int | None = Query(None, ge=1, le=5000),
    _: str = Depends(require_access),
):
    parsed = None if not opportunity_ids else [item.strip() for item in opportunity_ids.split(",") if item.strip()]
    with SessionLocal() as session:
        result = InstitutionalDynamicManagementService(session).generate(opportunity_ids=parsed, limit=limit)
        session.commit()
        return envelope(request, result.__dict__)


@router.get("/opportunities/{opportunity_id}/management", response_model=ApiEnvelope)
def get_management(opportunity_id: str, request: Request, _: str = Depends(require_access)):
    with SessionLocal() as session:
        execution = session.query(ExecutionRecommendationModel).filter_by(opportunity_id=opportunity_id).first()
        snapshots = session.query(PositionManagementSnapshotModel).filter_by(opportunity_id=opportunity_id).order_by(PositionManagementSnapshotModel.created_at.desc()).all()
        valuations = session.query(StrategyValuationModel).filter_by(opportunity_id=opportunity_id).order_by(StrategyValuationModel.strategy_score.desc()).all()
        return envelope(request, {
            "execution_recommendation": None if execution is None else dict(execution.payload_json or {}),
            "management_snapshots": [dict(row.payload_json or {}) for row in snapshots],
            "strategy_valuations": [dict(row.payload_json or {}) for row in valuations],
        })

@router.post("/opportunities/{opportunity_id}/handoff/trade-builder", response_model=ApiEnvelope)
def handoff_trade_builder(
    opportunity_id: str,
    payload: dict,
    request: Request,
    actor: str = Depends(require_mutation_access),
):
    from .handoff import InstitutionalOptionsHandoffService
    try:
        with SessionLocal() as session:
            result = InstitutionalOptionsHandoffService(session).create_trade_plan(
                opportunity_id,
                account_id=str(payload["account_id"]),
                capital=float(payload["capital"]),
                risk_budget_pct=float(payload["risk_budget_pct"]),
                actor=actor,
                overrides=dict(payload.get("overrides") or {}),
            )
            return envelope(request, result.__dict__)
    except KeyError as exc:
        raise HTTPException(422, f"Missing required field: {exc.args[0]}") from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/handoffs/{handoff_id}/execution-intent", response_model=ApiEnvelope)
def handoff_execution_intent(
    handoff_id: str,
    payload: dict,
    request: Request,
    actor: str = Depends(require_mutation_access),
):
    from .handoff import InstitutionalOptionsHandoffService
    try:
        with SessionLocal() as session:
            result = InstitutionalOptionsHandoffService(session).create_execution_intent(
                handoff_id, actor=actor, portfolio_id=payload.get("portfolio_id")
            )
            return envelope(request, result.__dict__)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc

@router.post("/outcomes/capture", response_model=ApiEnvelope)
def capture_outcome(
    payload: dict,
    request: Request,
    actor: str = Depends(require_mutation_access),
):
    from .outcome_learning import InstitutionalOptionsOutcomeLearningService, OutcomeObservationInput
    try:
        with SessionLocal() as session:
            result = InstitutionalOptionsOutcomeLearningService(session).capture(OutcomeObservationInput(
                opportunity_id=str(payload["opportunity_id"]),
                entry_timestamp=str(payload["entry_timestamp"]),
                exit_timestamp=str(payload["exit_timestamp"]),
                underlying_entry=float(payload["underlying_entry"]),
                underlying_exit=float(payload["underlying_exit"]),
                option_entry_value=float(payload["option_entry_value"]),
                option_exit_value=float(payload["option_exit_value"]),
                quantity=float(payload["quantity"]),
                exit_reason=str(payload["exit_reason"]),
                mfe_pct=None if payload.get("mfe_pct") is None else float(payload["mfe_pct"]),
                mae_pct=None if payload.get("mae_pct") is None else float(payload["mae_pct"]),
                management_policy=str(payload.get("management_policy") or "UNDERLYING_DYNAMIC"),
                metadata={"actor": actor, **dict(payload.get("metadata") or {})},
            ))
            session.commit()
            return envelope(request, result.__dict__)
    except KeyError as exc:
        raise HTTPException(422, f"Missing required field: {exc.args[0]}") from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/learning/summarize", response_model=ApiEnvelope)
def summarize_learning(
    request: Request,
    scope: str = "ALL",
    scope_value: str | None = None,
    _: str = Depends(require_access),
):
    from .outcome_learning import InstitutionalOptionsOutcomeLearningService
    with SessionLocal() as session:
        result = InstitutionalOptionsOutcomeLearningService(session).summarize(scope=scope, scope_value=scope_value)
        session.commit()
        return envelope(request, result.__dict__)


@router.post("/decisions/build", response_model=ApiEnvelope)
def build_decisions(
    request: Request,
    opportunity_ids: str | None = None,
    limit: int | None = Query(None, ge=1, le=5000),
    _: str = Depends(require_access),
):
    parsed = None if not opportunity_ids else [item.strip() for item in opportunity_ids.split(",") if item.strip()]
    with SessionLocal() as session:
        result = InstitutionalDecisionService(session).build(opportunity_ids=parsed, limit=limit)
        session.commit()
        return envelope(request, result.__dict__)


@router.get("/opportunities/{opportunity_id}/decision", response_model=ApiEnvelope)
def get_decision(opportunity_id: str, request: Request, _: str = Depends(require_access)):
    with SessionLocal() as session:
        row = session.query(InstitutionalDecisionSnapshotModel).filter_by(opportunity_id=opportunity_id).first()
        if row is None:
            raise HTTPException(404, "Institutional decision snapshot not found")
        return envelope(request, dict(row.payload_json or {}))
