import argparse
from sqlalchemy import select, func
from trading_ai.database.session import SessionLocal
from trading_ai.stock_intelligence.models import StockScannerPublicationModel
from trading_ai.institutional_options.models import InstitutionalOpportunityModel

def latest_stock_run(session):
    row = session.scalars(select(StockScannerPublicationModel).where(StockScannerPublicationModel.publication_name=='current_stock_intelligence').order_by(StockScannerPublicationModel.snapshot_timestamp.desc()).limit(1)).first()
    if not row or row.status != 'READY':
        return None
    return str(row.scanner_run_id)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--capture-current-stock-run',action='store_true'); p.add_argument('--expected-stock-run-id'); a=p.parse_args()
    with SessionLocal() as s:
        current=latest_stock_run(s)
        if a.capture_current_stock_run:
            if not current: raise SystemExit('current_stock_intelligence is not READY')
            print(current); return
        if not a.expected_stock_run_id: raise SystemExit('--expected-stock-run-id is required')
        if current != a.expected_stock_run_id: raise SystemExit(f'LINEAGE_DRIFT: expected {a.expected_stock_run_id}, observed {current}')
        count=s.scalar(select(func.count()).select_from(InstitutionalOpportunityModel).where(InstitutionalOpportunityModel.stock_scanner_run_id==a.expected_stock_run_id)) or 0
        if count <= 0: raise SystemExit(f'NO_CURRENT_M62_OPPORTUNITIES_FOR_LINEAGE: {a.expected_stock_run_id}')
        print(f'LINEAGE_OK stock_scanner_run_id={current} opportunity_count={count}')
if __name__=='__main__': main()
