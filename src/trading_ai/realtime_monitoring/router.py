from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from trading_ai.production_api.security import require_access, require_mutation_access

router=APIRouter(prefix='/api/v1/realtime',tags=['realtime-monitoring'])
def svc(request:Request): return request.app.state.m42_service

@router.get('/snapshot')
def snapshot(request:Request,_:str=Depends(require_access)): return svc(request).snapshot().model_dump(mode='json')
@router.get('/alerts')
def alerts(request:Request,_:str=Depends(require_access)): return {'alerts':[a.model_dump(mode='json') for a in svc(request).alerts.values()]}
@router.get('/events')
def events(request:Request,limit:int=100,_:str=Depends(require_access)): return {'events':[e.model_dump(mode='json') for e in svc(request).bus.history(limit)]}
@router.post('/alerts/{alert_id}/acknowledge')
def acknowledge(alert_id:str,request:Request,actor:str=Depends(require_mutation_access)):
    if alert_id not in svc(request).alerts: raise HTTPException(404,'Alert not found')
    return svc(request).acknowledge(alert_id,actor).model_dump(mode='json')
@router.post('/alerts/{alert_id}/resolve')
def resolve(alert_id:str,request:Request,actor:str=Depends(require_mutation_access)):
    if alert_id not in svc(request).alerts: raise HTTPException(404,'Alert not found')
    return svc(request).resolve(alert_id).model_dump(mode='json')
@router.websocket('/stream')
async def stream(ws:WebSocket):
    settings=ws.app.state.m40_settings
    if settings.require_api_key and ws.query_params.get('api_key')!=settings.api_key:
        await ws.close(code=4401); return
    await ws.accept(); queue=ws.app.state.m42_service.bus.subscribe()
    try:
        await ws.send_json({'event_type':'CONNECTED','payload':ws.app.state.m42_service.snapshot().model_dump(mode='json')})
        while True: await ws.send_json((await queue.get()).model_dump(mode='json'))
    except WebSocketDisconnect: pass
    finally: ws.app.state.m42_service.bus.unsubscribe(queue)
