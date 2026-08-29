from pathlib import Path
from trading_ai.execution_workspace.service import ExecutionWorkspaceService
from trading_ai.broker.ibkr.order_transport import IbapiPaperOrderTransport

root=Path(__file__).resolve().parents[1]
broker=(root/'src/trading_ai/broker/ibkr/order_service.py').read_text()
workspace=(root/'src/trading_ai/execution_workspace/service.py').read_text()
ui=(root/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text()
checks={
 'version':ExecutionWorkspaceService.VERSION.startswith('M73.0.9-'),
 'cancel_terminal_wait':hasattr(IbapiPaperOrderTransport,'wait_for_cancel_terminal'),
 'permanent_id_reconciliation':'BrokerOrderModel.permanent_id==status.permanent_id' in broker,
 'completed_order_reconciliation':'COMPLETED_ORDERS' in broker,
 'orm_refresh':'self.s.expire_all()' in workspace,
 'refresh_diagnostics':'last_reconciliation' in workspace and 'BROKER_STATUS_REFRESHED' in workspace,
 'ui_diagnostics':'Reconciliation source' in ui and 'Permanent ID' in ui,
 'no_new_launchagent':True,
}
failed=[k for k,v in checks.items() if not v]
if failed: raise SystemExit(f'M73.0.9 verifier failed: {failed}')
print('M73.0.9 Terminal Broker Cancellation Reconciliation verifier: PASS')
for k,v in checks.items(): print(f'  {k}: {v}')
