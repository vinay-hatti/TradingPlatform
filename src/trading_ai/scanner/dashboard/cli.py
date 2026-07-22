from __future__ import annotations
import argparse,json
from pathlib import Path
from .contracts import DashboardConfiguration,DashboardView,RankingRecord
from .service import ScannerDashboardService

def _load(path):
    if path is None:return []
    p=json.loads(path.read_text()); rows=p.get('rankings',p) if isinstance(p,dict) else p
    return [RankingRecord(str(r['symbol']).upper(),int(r.get('rank',i)),float(r.get('institutional_score',0)),float(r.get('probability_score',r.get('probability',0))),None if r.get('expected_move') is None else float(r['expected_move']),r.get('regime'),r.get('sector'),r.get('exchange'),r.get('optionable'),r.get('is_etf'),r.get('cross_asset_score'),r.get('metadata',{})) for i,r in enumerate(rows,1)]
def build_parser():
    p=argparse.ArgumentParser(description='Milestone 35 Phase 5 Step 1 scanner dashboard framework'); p.add_argument('--universe-name',default='US_ACTIVE_EQUITIES_ETFS'); p.add_argument('--universe-size',type=int,default=0); p.add_argument('--top-n',type=int,choices=(10,25,50,100),default=50); p.add_argument('--rankings-json',type=Path); p.add_argument('--output-dir',type=Path,default=Path('reports/m35/phase5/dashboard')); p.add_argument('--completed',type=int,default=0); p.add_argument('--failed',type=int,default=0); p.add_argument('--skipped',type=int,default=0); p.add_argument('--elapsed-seconds',type=float,default=0.0); p.add_argument('--complete',action='store_true'); return p
def run(argv=None):
    a=build_parser().parse_args(argv); svc=ScannerDashboardService(output_dir=a.output_dir); s=svc.create_session(DashboardConfiguration(top_n=a.top_n)); s=svc.initialize(s,universe_name=a.universe_name,universe_size=a.universe_size); s=svc.start(s); s=svc.update_progress(s,symbols_completed=a.completed,symbols_failed=a.failed,symbols_skipped=a.skipped,elapsed_seconds=a.elapsed_seconds); ranks=_load(a.rankings_json)
    if ranks:s=svc.update_rankings(s,ranks); s=svc.navigate(s,DashboardView.RANKINGS)
    if a.complete:s=svc.complete(s)
    print(json.dumps({'session_id':s.session.session_id,'status':s.session.status.value,'completion_pct':s.progress.completion_pct,'ranking_count':len(s.rankings),'output_dir':str(a.output_dir)},indent=2)); return 0
