from __future__ import annotations
from pathlib import Path
from .serialization import read_json, write_json_atomic
from .profile import utc_now_iso

class ExecutionOrchestrationReportingService:
    def generate(self,output_dir:Path)->dict:
        queue=read_json(output_dir/'execution_queue.json'); events=read_json(output_dir/'execution_events.json'); result=read_json(output_dir/'workflow_result.json')
        orders=queue.get('orders',[]); statuses={}
        for order in orders: statuses[order.get('status','UNKNOWN')]=statuses.get(order.get('status','UNKNOWN'),0)+1
        report={'milestone':'38','status':result.get('status','UNKNOWN'),'trading_control':result.get('trading_control','UNKNOWN'),'order_count':len(orders),'status_counts':statuses,'event_count':len(events.get('events',[])),'generated_at':utc_now_iso(),'orders':orders}
        write_json_atomic(output_dir/'milestone38_closure.json',report)
        rows=''.join(f'<tr><td>{k}</td><td>{v}</td></tr>' for k,v in sorted(statuses.items()))
        html=f'''<!doctype html><html><head><meta charset="utf-8"><title>Milestone 38</title><style>body{{font-family:Arial;margin:32px}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:8px}}</style></head><body><h1>Milestone 38 Execution Orchestration</h1><p><b>Status:</b> {report['status']}</p><p><b>Trading control:</b> {report['trading_control']}</p><table><tr><th>Order status</th><th>Count</th></tr>{rows}</table><p>Events: {report['event_count']}</p></body></html>'''
        (output_dir/'milestone38_closure.html').write_text(html,encoding='utf-8'); return report
