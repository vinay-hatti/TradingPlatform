import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from trading_ai.scanner.universe_management import SecurityProfile, UniverseProviderResult, UniverseReconciliationEngine, write_reconciliation_json

def main():
 r=UniverseReconciliationEngine().reconcile((UniverseProviderResult('CSV',datetime.now(timezone.utc),(SecurityProfile('MSFT',exchange='NASDAQ',source='CSV'),)),))
 with TemporaryDirectory() as d:
  p=write_reconciliation_json(r,Path(d)/'r.json'); data=json.loads(p.read_text()); assert data['metadata']['unique_symbol_count']==1
 print('Milestone 35 Phase 1 Step 2 reporting assertions passed.')
if __name__=='__main__': main()
