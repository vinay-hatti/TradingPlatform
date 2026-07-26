from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from trading_ai.production_api.security import require_access, require_mutation_access
router=APIRouter(prefix='/api/v1/market-overview',tags=['market-overview'])

def service(request:Request): return request.app.state.m45_market_overview_service

def envelope(request:Request,data,**metadata): return {'request_id':request.state.request_id,'data':data,'metadata':metadata}

@router.get('/latest')
def latest(request:Request,_:str=Depends(require_access),svc=Depends(service)):
    return envelope(request,svc.latest(),source='PostgreSQL')

@router.post('/refresh')
def refresh(request:Request,_:str=Depends(require_mutation_access),svc=Depends(service)):
    return envelope(request,svc.build(persist=True).to_dict(),source='PostgreSQL')

@router.get('/scanner-context')
def scanner_context(request:Request,_:str=Depends(require_access),svc=Depends(service)):
    return envelope(request,svc.scanner_context(),source='market_overview_snapshot')
