from __future__ import annotations
from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException,Request,Query
from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from trading_ai.production_api.security import require_access,require_mutation_access
from trading_ai.opportunity_domain.service import OpportunityService
from .engines import InstitutionalIntelligenceService
from .models import IntelligenceSnapshotModel
from .repository import IntelligenceRepository
router=APIRouter(prefix='/api/v1/institutional-intelligence',tags=['institutional-intelligence'])
def env(req,data,**meta): return ApiEnvelope(request_id=req.state.request_id,data=data,metadata=meta)
def opp_dict(record):
 d=record.__dict__.copy();d['source_payload']=d.pop('source_payload_json',{});d['metadata']=d.pop('metadata_json',{});return d
@router.post('/opportunities/{opportunity_id}/generate',response_model=ApiEnvelope)
def generate(opportunity_id:str,request:Request,actor:str=Depends(require_mutation_access)):
 with SessionLocal() as session:
  os=OpportunityService(session); model=os.repo.get(opportunity_id)
  if model is None: raise HTTPException(404,'Opportunity not found')
  bundle=InstitutionalIntelligenceService().generate(opp_dict(model)); payload=bundle.to_dict(); repo=IntelligenceRepository(session)
  existing=repo.latest(opportunity_id)
  if existing and existing.opportunity_version==model.version and existing.analytics_version==bundle.analytics_version: return env(request,existing.payload_json,cached=True)
  item=IntelligenceSnapshotModel(intelligence_id=f'IIF-{uuid4().hex.upper()}',opportunity_id=opportunity_id,opportunity_version=model.version,snapshot_id=model.snapshot_id,snapshot_timestamp=model.snapshot_timestamp,analytics_version=bundle.analytics_version,generated_at=bundle.generated_at,generated_by=actor,payload_json=payload);repo.add(item);session.commit();return env(request,payload,cached=False)
@router.get('/opportunities/{opportunity_id}',response_model=ApiEnvelope)
def latest(opportunity_id:str,request:Request,generate_if_missing:bool=Query(True),_:str=Depends(require_access)):
 with SessionLocal() as session:
  repo=IntelligenceRepository(session); item=repo.latest(opportunity_id)
  if item:return env(request,item.payload_json,intelligence_id=item.intelligence_id)
  os=OpportunityService(session);model=os.repo.get(opportunity_id)
  if model is None:raise HTTPException(404,'Opportunity not found')
  if not generate_if_missing:raise HTTPException(404,'Intelligence not generated')
  payload=InstitutionalIntelligenceService().generate(opp_dict(model)).to_dict();return env(request,payload,ephemeral=True)
@router.get('/opportunities/{opportunity_id}/history',response_model=ApiEnvelope)
def history(opportunity_id:str,request:Request,limit:int=Query(20,ge=1,le=100),_:str=Depends(require_access)):
 with SessionLocal() as session:
  items=IntelligenceRepository(session).list(opportunity_id,limit);return env(request,[{'intelligence_id':x.intelligence_id,'opportunity_version':x.opportunity_version,'analytics_version':x.analytics_version,'generated_at':x.generated_at,'generated_by':x.generated_by,'health':x.payload_json.get('health',{})} for x in items],count=len(items))
