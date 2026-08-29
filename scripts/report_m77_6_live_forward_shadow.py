from __future__ import annotations
import json
from sqlalchemy import text
from trading_ai.database.session import SessionLocal
with SessionLocal() as s:
    summary=[dict(x) for x in s.execute(text('SELECT shadow_tier,status,horizon_sessions,COUNT(*) n FROM m77_shadow_signals GROUP BY 1,2,3 ORDER BY 1,3,2')).mappings()]
    perf=[dict(x) for x in s.execute(text('SELECT s.shadow_tier,s.candidate_horizon_id,s.horizon_sessions,COUNT(*) n,ROUND(AVG(o.thesis_return_pct)::numeric,4) avg_return_pct,ROUND((AVG(CASE WHEN o.directional_hit THEN 1.0 ELSE 0.0 END)*100)::numeric,2) hit_rate_pct FROM m77_shadow_outcomes o JOIN m77_shadow_signals s ON s.signal_id=o.signal_id GROUP BY 1,2,3 ORDER BY 1,3,2')).mappings()]
print('=== M77.6 LIVE FORWARD SHADOW INTELLIGENCE ===')
print(json.dumps({'signal_counts':summary,'matured_performance':perf,'production_champion_change':False},default=str,indent=2))
