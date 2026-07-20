from fastapi import APIRouter,Depends,HTTPException
from trading_ai.ui.models.operations_command_center import ReleaseRequest,RuntimeApprovalRequest,RuntimeControlRequest
from trading_ai.ui.models.paper_commands import GovernedActor
from trading_ai.ui.services.operations_command_center_service import OperationsCommandCenterService
router=APIRouter(prefix='/api/v1/operations',tags=['operations'])
def service(): return OperationsCommandCenterService()
@router.get('/health')
def health(svc=Depends(service)): return svc.health_topology()
@router.get('/runtime-controls')
def runtime_controls(svc=Depends(service)): return svc.list_runtime_controls()
@router.post('/runtime-controls')
def request_control(request:RuntimeControlRequest,svc=Depends(service)):
    try:return svc.request_runtime_control(request)
    except PermissionError as e:raise HTTPException(403,str(e))
@router.post('/runtime-controls/{request_id}/approval')
def approve(request_id:str,request:RuntimeApprovalRequest,svc=Depends(service)):
    try:return svc.approve_runtime_control(request_id,request)
    except KeyError:raise HTTPException(404,'Runtime control request not found')
    except PermissionError as e:raise HTTPException(403,str(e))
@router.post('/runtime-controls/{request_id}/execute')
def execute(request_id:str,actor:GovernedActor,svc=Depends(service)):
    try:return svc.execute_runtime_control(request_id,actor)
    except KeyError:raise HTTPException(404,'Runtime control request not found')
    except PermissionError as e:raise HTTPException(403,str(e))
    except ValueError as e:raise HTTPException(422,str(e))
@router.get('/incidents')
def incidents(svc=Depends(service)): return svc.list_incidents()
@router.get('/alerts')
def alerts(svc=Depends(service)): return svc.list_alerts()
@router.get('/releases')
def releases(svc=Depends(service)): return svc.list_releases()
@router.post('/releases')
def register_release(request:ReleaseRequest,svc=Depends(service)):
    try:return svc.register_release(request)
    except PermissionError as e:raise HTTPException(403,str(e))
@router.get('/locks')
def locks(svc=Depends(service)): return svc.list_locks()
