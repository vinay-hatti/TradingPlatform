import json,tempfile
from pathlib import Path
from trading_ai.position_management.service import PositionMonitoringService
from trading_ai.position_management.reporting_service import PositionManagementReportingService

def main():
    with tempfile.TemporaryDirectory() as d:
      p=Path(d); reg=p/'registry.json'; marks=p/'marks.json'; risk=p/'risk.json'; out=p/'out'
      reg.write_text(json.dumps({"positions":[{"position_id":"P1","portfolio_id":"PRIMARY","symbol":"NVDA","strategy_type":"LONG_CALL","direction":"BULLISH","status":"OPEN","quantity":3,"entry_price":2.0,"opened_at":"2026-07-01T00:00:00+00:00","updated_at":"2026-07-22T00:00:00+00:00"}]}))
      marks.write_text(json.dumps({"marks":[{"position_id":"P1","symbol":"NVDA","price":3.2,"marked_at":"2099-01-01T00:00:00+00:00"}]})); risk.write_text(json.dumps({"trading_control":"ALLOW"}))
      result=PositionMonitoringService().run(str(reg),str(marks),str(out),str(risk))
      data=json.loads(Path(result.instruction_file).read_text()); assert len(data['instructions'])==1
      assert data['instructions'][0]['status']=='PENDING_RISK_GATE' and data['instructions'][0]['metadata']['execution_route']=='M38'
      report=PositionManagementReportingService().render(result.assessment_file,result.instruction_file,result.report_file)
      assert 'Milestone 39' in Path(report).read_text()
      print("M39 instructions and workflow assertions passed.")
if __name__=="__main__": main()
