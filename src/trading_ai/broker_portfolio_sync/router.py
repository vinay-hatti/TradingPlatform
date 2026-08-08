from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select

from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from trading_ai.production_api.security import require_access, require_mutation_access

from .models import BrokerCurrentPositionModel, BrokerPortfolioAlertModel, BrokerPortfolioPublicationModel
from .service import BrokerPortfolioSynchronizationService

router = APIRouter(prefix="/api/v1/broker-portfolio", tags=["broker-portfolio"])


def env(request: Request, data, **metadata):
    return ApiEnvelope(request_id=request.state.request_id, data=data, metadata=metadata)


@router.post("/synchronize", response_model=ApiEnvelope)
def synchronize(
    request: Request,
    payload: dict | None = None,
    actor: str = Depends(require_mutation_access),
):
    payload = payload or {}
    try:
        result = BrokerPortfolioSynchronizationService(SessionLocal).synchronize(
            payload.get("portfolio_id", "PAPER-PRIMARY"),
            actor=actor,
            connect_broker=bool(payload.get("connect_broker", True)),
        )
        return env(request, result)
    except Exception as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/positions", response_model=ApiEnvelope)
def positions(
    request: Request,
    portfolio_id: str = Query("PAPER-PRIMARY"),
    active_only: bool = Query(True),
    _: str = Depends(require_access),
):
    with SessionLocal() as session:
        statement = select(BrokerCurrentPositionModel).where(
            BrokerCurrentPositionModel.portfolio_id == portfolio_id
        )
        if active_only:
            statement = statement.where(BrokerCurrentPositionModel.active.is_(True))
        rows = list(session.scalars(statement.order_by(BrokerCurrentPositionModel.symbol)).all())
        data = [{column.name: getattr(row, column.name) for column in row.__table__.columns} for row in rows]
        return env(request, data, count=len(data))


@router.get("/publication", response_model=ApiEnvelope)
def publication(
    request: Request,
    portfolio_id: str = Query("PAPER-PRIMARY"),
    _: str = Depends(require_access),
):
    with SessionLocal() as session:
        row = session.scalar(
            select(BrokerPortfolioPublicationModel)
            .where(BrokerPortfolioPublicationModel.portfolio_id == portfolio_id)
            .order_by(BrokerPortfolioPublicationModel.published_at.desc())
            .limit(1)
        )
        data = None if row is None else {column.name: getattr(row, column.name) for column in row.__table__.columns}
        return env(request, data)


@router.get("/alerts", response_model=ApiEnvelope)
def alerts(
    request: Request,
    portfolio_id: str = Query("PAPER-PRIMARY"),
    status: str = Query("OPEN"),
    _: str = Depends(require_access),
):
    with SessionLocal() as session:
        rows = list(session.scalars(
            select(BrokerPortfolioAlertModel).where(
                BrokerPortfolioAlertModel.portfolio_id == portfolio_id,
                BrokerPortfolioAlertModel.status == status,
            ).order_by(BrokerPortfolioAlertModel.created_at.desc())
        ).all())
        data = [{column.name: getattr(row, column.name) for column in row.__table__.columns} for row in rows]
        return env(request, data, count=len(data))
