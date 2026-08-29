from pathlib import Path
from tempfile import TemporaryDirectory
from trading_ai.ui.models.paper_commands import GovernedActor
from trading_ai.ui.models.operations_command_center import RuntimeControlRequest,RuntimeApprovalRequest,ReleaseRequest
from trading_ai.ui.services.operations_command_center_service import OperationsCommandCenterService

def main():
 operator=GovernedActor(user_id='operator',session_id='s1',roles=['OPERATOR'],permissions=['operations.runtime.request','operations.runtime.execute'])
 approver=GovernedActor(user_id='approver',session_id='s2',roles=['OPS_APPROVER'],permissions=['operations.runtime.approve','operations.release.register','operations.lock.acquire'])
 with TemporaryDirectory() as d:
  svc=OperationsCommandCenterService(Path(d)/'state.json',Path(d)/'audit.jsonl')
  h=svc.health_topology();assert h.overall_status=='HEALTHY' and len(h.services)>=10
  req=svc.request_runtime_control(RuntimeControlRequest(service_id='scanner',action='PAUSE',reason='Controlled maintenance',confirmation_token='CONFIRM-OPS-123',actor=operator));assert req.status=='REQUESTED'
  try:svc.approve_runtime_control(req.request_id,RuntimeApprovalRequest(decision='APPROVE',reason='Self approval',confirmation_token='CONFIRM-OPS-123',actor=operator));raise AssertionError
  except PermissionError:pass
  approved=svc.approve_runtime_control(req.request_id,RuntimeApprovalRequest(decision='APPROVE',reason='Independent approval',confirmation_token='CONFIRM-OPS-123',actor=approver));assert approved.status=='APPROVED'
  executed=svc.execute_runtime_control(req.request_id,operator);assert executed.status=='EXECUTED';assert svc.health_topology().overall_status=='DEGRADED'
  rel=svc.register_release(ReleaseRequest(release_version='33.7.0',git_commit='abcdef1234567',installer_version='33.7.0',package_sha256='a'*64,reason='Register validated package',actor=approver));assert rel.status=='REGISTERED'
  lock=svc.acquire_lock('deployment','Phase 7 test',approver,5);assert lock.lock_name=='deployment'
 print('All Milestone 33 Phase 7 Operations Command Center assertions passed.')
if __name__=='__main__':main()
