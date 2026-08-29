#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import defaultdict
from sqlalchemy import text
from trading_ai.database.session import SessionLocal

with SessionLocal() as s:
    counts=s.execute(text("""
      SELECT baseline_source,horizon_sessions,status,count(*) AS n
      FROM m77_13_forward_signals
      GROUP BY baseline_source,horizon_sessions,status
      ORDER BY baseline_source,horizon_sessions,status
    """)).mappings().all()
    perf=s.execute(text("""
      SELECT s.baseline_source,s.horizon_sessions,count(*) AS n,
             avg(o.thesis_return_pct) AS avg_thesis_return_pct,
             100.0*avg(CASE WHEN o.directional_hit THEN 1.0 ELSE 0.0 END) AS hit_rate_pct
      FROM m77_13_forward_signals s
      JOIN m77_13_forward_outcomes o ON o.signal_id=s.signal_id
      GROUP BY s.baseline_source,s.horizon_sessions
      ORDER BY s.baseline_source,s.horizon_sessions
    """)).mappings().all()
    role=s.execute(text("""
      SELECT baseline_source,horizon_sessions,payload_json
      FROM m77_13_forward_signals
      WHERE status='MATURED'
    """)).mappings().all()

print("=== M77.13 MULTI-CADENCE CERTIFIED-BASELINE FORWARD SHADOW ===")
print(json.dumps({
  "signal_counts":[dict(x) for x in counts],
  "matured_performance":[{k:(float(v) if hasattr(v,"as_tuple") else v) for k,v in dict(x).items()} for x in perf],
  "production_champion_change":False,
  "production_filter_or_ranking_effect":False,
},indent=2,default=str))
