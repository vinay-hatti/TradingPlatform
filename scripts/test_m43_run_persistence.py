from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.daily_scan_workstation.models import RunKind, RunStatus, ScannerRun
from trading_ai.daily_scan_workstation.service import DailyScanWorkstationService

with TemporaryDirectory() as tmp:
    root=Path(tmp)
    service=DailyScanWorkstationService(root, root/'reports')
    run=ScannerRun(run_id='test-run',kind=RunKind.DAILY_SCAN,status=RunStatus.SUCCEEDED,requested_by='test',request={},summary={'candidate_count':3})
    service._save(run)
    restored=service.get('test-run')
    assert restored.status==RunStatus.SUCCEEDED
    assert restored.summary['candidate_count']==3
    assert service.list_runs()[0].run_id=='test-run'
print('Milestone 43 run persistence assertions passed.')
