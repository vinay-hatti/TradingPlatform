from fastapi import APIRouter, Depends, HTTPException, Query, Request
from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from trading_ai.production_api.security import require_access, require_mutation_access
from .service import DynamicPositionManagementService

router=APIRouter(prefix='/api/v1/dynamic-position-management',tags=['dynamic-position-management'])
def env(r,d,**m):return ApiEnvelope(request_id=r.state.request_id,data=d,metadata=m)
def fail(e):return HTTPException(404 if isinstance(e,KeyError) else 409,str(e))

@router.get('/instructions',response_model=ApiEnvelope)
def instructions(request:Request,position_id:str|None=Query(None),status:str|None=Query(None),_:str=Depends(require_access)):
 with SessionLocal() as s:
  items=DynamicPositionManagementService(s).list_instructions(position_id,status);return env(request,items,count=len(items))

@router.post('/positions/{position_id}/automation-mode',response_model=ApiEnvelope)
def mode(position_id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,DynamicPositionManagementService(s).set_mode(position_id,payload['mode'],actor,payload.get('reason','Automation mode updated')))
 except Exception as e:raise fail(e)

@router.post('/positions/{position_id}/evaluate',response_model=ApiEnvelope)
def evaluate(position_id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:
   item=DynamicPositionManagementService(s).evaluate_position(position_id,actor,bool(payload.get('submit_automatic',True)));s.commit();return env(request,item.to_dict())
 except Exception as e:raise fail(e)

@router.post('/cycles',response_model=ApiEnvelope)
def cycle(payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:
   result=DynamicPositionManagementService(s).evaluate_all(payload.get('portfolio_id'),payload.get('position_ids'),actor,bool(payload.get('submit_automatic',True)),int(payload.get('limit',250)));return env(request,result.to_dict())
 except Exception as e:raise fail(e)

@router.post('/instructions/{instruction_id}/approve',response_model=ApiEnvelope)
def approve(instruction_id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,DynamicPositionManagementService(s).approve_instruction(instruction_id,actor,payload.get('reason','Approved dynamic exit instruction'),bool(payload.get('submit',False))))
 except Exception as e:raise fail(e)
