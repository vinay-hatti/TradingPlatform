import json
from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters
from trading_ai.ui.api.execution_console import service as execution_dependency
from trading_ai.ui.app import create_app
from trading_ai.ui.services.execution_console_service import ExecutionConsoleService

def main():
    with TemporaryDirectory() as directory:
        root=Path(directory); execution=root/"reports/execution"; execution.mkdir(parents=True)
        (execution/"orders.json").write_text(json.dumps({"orders":[
            {"order_id":"O1","symbol":"SPY","side":"BUY","order_type":"LIMIT","quantity":2,"filled_quantity":2,"limit_price":5.0,"average_fill_price":4.95,"status":"FILLED","submitted_at":"2026-07-18T14:00:00+00:00","updated_at":"2026-07-18T14:00:03+00:00"},
            {"order_id":"O2","symbol":"QQQ","side":"SELL","order_type":"LIMIT","quantity":1,"filled_quantity":0,"limit_price":6.0,"status":"REJECTED","submitted_at":"2026-07-18T14:01:00+00:00","updated_at":"2026-07-18T14:01:01+00:00"}
        ]}),encoding="utf-8")
        (execution/"fills.json").write_text(json.dumps({"fills":[
            {"fill_id":"F1","order_id":"O1","symbol":"SPY","quantity":2,"price":4.95,"commission":1.30,"filled_at":"2026-07-18T14:00:03+00:00"}
        ]}),encoding="utf-8")
        (execution/"execution_quality.json").write_text(json.dumps({"average_fill_latency_ms":3000,"average_slippage_bps":-10,"total_slippage":-10,"reconciliation_breaks":1}),encoding="utf-8")
        service=ExecutionConsoleService(RepositoryArtifactAdapters(root),stale_after_seconds=999999999,stale_order_seconds=999999999)
        result=service.get()
        assert result.available
        assert result.quality.submitted_orders==2
        assert result.quality.filled_orders==1
        assert result.quality.rejected_orders==1
        assert result.quality.reconciliation_breaks==1
        assert len(result.fills)==1
        assert any(a.code=="ORDER_REJECTED" for a in result.alerts)
        readonly=service.cancel("O1",__import__("trading_ai.ui.models.execution_console",fromlist=["CancelOrderRequest"]).CancelOrderRequest())
        assert readonly.accepted is False
        app=create_app();app.dependency_overrides[execution_dependency]=lambda:service
        response=TestClient(app).get("/api/v1/execution")
        assert response.status_code==200,response.text
        assert response.json()["quality"]["submitted_orders"]==2
        app.dependency_overrides.clear()
    print("All Milestone 31 Phase 6 Execution Console assertions passed.")

if __name__=="__main__": main()
