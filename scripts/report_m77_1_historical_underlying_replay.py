from sqlalchemy import text
from trading_ai.database import SessionLocal
import json
with SessionLocal() as s:
 run=s.execute(text("SELECT * FROM historical_underlying_replay_run ORDER BY started_at DESC LIMIT 1")).mappings().one_or_none()
 if not run: raise SystemExit('No M77.1 replay run found')
 rid=run['replay_run_id']
 summary=s.execute(text("""SELECT count(*) n, count(*) FILTER (WHERE o.status='REALIZED') realized, count(*) FILTER (WHERE o.entry_triggered) entries, count(*) FILTER (WHERE o.ambiguous_same_bar) ambiguous, avg(o.return_5d_pct) r5,avg(o.return_10d_pct) r10,avg(o.return_20d_pct) r20,avg(o.return_40d_pct) r40,avg(o.return_60d_pct) r60,avg(o.mfe_pct) mfe,avg(o.mae_pct) mae FROM historical_underlying_replay_outcome o WHERE replay_run_id=:r"""),{'r':rid}).mappings().one()
 bydir=s.execute(text("""SELECT p.direction,count(*) n,avg(o.return_20d_pct) avg_20d,avg(o.return_60d_pct) avg_60d FROM historical_underlying_replay_prediction p JOIN historical_underlying_replay_outcome o USING(prediction_id) WHERE p.replay_run_id=:r GROUP BY p.direction ORDER BY p.direction"""),{'r':rid}).mappings().all()
 print('=== M77.1 HISTORICAL UNDERLYING CHAMPION BASELINE ==='); print(json.dumps({'run':dict(run),'summary':dict(summary),'by_direction':[dict(x) for x in bydir]},default=str,indent=2))
