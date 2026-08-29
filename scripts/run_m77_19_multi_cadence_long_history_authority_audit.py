#!/usr/bin/env python3
import json
from pathlib import Path
from sqlalchemy import text
from trading_ai.database.session import SessionLocal
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/m77/m77_19_multi_cadence_long_history_replication_authority_audit.json"
START="2003-09-10"; END="2026-08-21"

def load(p):
 p=ROOT/p
 try:return json.loads(p.read_text())
 except:return None
def ids(x,key):
 if not x:return []
 if key=="weekly":return list(x.get("replay_run_ids") or [])
 return [x["replay_run_id"]] if x.get("replay_run_id") else []
wm=load("reports/m77/m77_2_multiyear_frozen_champion_manifest.json")
dm=load("reports/m77/m77_9_daily_model_replay_manifest.json")
mm=load("reports/m77/m77_10_monthly_model_replay_manifest.json")
pit=load("reports/m77/m77_8_daily_pit_regime_snapshots.json")
m11=load("reports/m77/m77_11_multi_cadence_confluence_conflict_study.json")
m12=load("reports/m77/m77_12_cadence_role_incremental_utility_certification.json")
rids={"daily":ids(dm,"daily"),"weekly":ids(wm,"weekly"),"monthly":ids(mm,"monthly")}
with SessionLocal() as s:
 def cov(v):
  if not v:return {"rows":0,"first_as_of":None,"last_as_of":None,"symbols":0}
  r=s.execute(text("SELECT count(*) n,min(as_of) a,max(as_of) b,count(DISTINCT symbol) syms FROM historical_underlying_replay_prediction WHERE replay_run_id = ANY(:x)"),{"x":v}).mappings().one()
  return {"rows":int(r["n"] or 0),"first_as_of":str(r["a"])[:10] if r["a"] else None,"last_as_of":str(r["b"])[:10] if r["b"] else None,"symbols":int(r["syms"] or 0)}
 coverage={k:cov(v) for k,v in rids.items()}
pd=[str(x.get("as_of",""))[:10] for x in (pit or {}).get("snapshots",[]) if x.get("as_of")]
pc={"rows":len(pd),"first_as_of":min(pd) if pd else None,"last_as_of":max(pd) if pd else None}
def spans(x):return bool(x["first_as_of"] and x["last_as_of"] and x["first_as_of"]<=START and x["last_as_of"]>=END)
gates={f"{k}_replay_states_cover_long_history":spans(v) for k,v in coverage.items()}
gates["pit_regime_states_cover_long_history"]=spans(pc)
gates["m77_11_frozen_report_present"]=m11 is not None
gates["m77_12_frozen_report_present"]=m12 is not None
exact=all(gates.values())
gaps=[]
for k,v in coverage.items():
 if not spans(v):gaps.append({"authority":k.upper()+"_REPLAY_STATES","available":v,"required":[START,END]})
if not spans(pc):gaps.append({"authority":"PIT_REGIME_STATES","available":pc,"required":[START,END]})
out={"version":"M77.19-MULTI-CADENCE-LONG-HISTORY-REPLICATION-AUTHORITY-AUDIT-1.0","status":"READY",
"cadence_state_coverage":coverage,"pit_regime_coverage":pc,"gates":gates,"authority_gaps":gaps,
"exact_5773_session_replication_authorized":exact,
"original_M77_11":{"coverage":(m11 or {}).get("coverage"),"summary":(m11 or {}).get("summary"),"methodology":(m11 or {}).get("methodology")},
"original_M77_12":{"coverage":(m12 or {}).get("coverage"),"summary":(m12 or {}).get("summary"),"methodology":(m12 or {}).get("methodology")},
"disposition":"AUTHORIZED_BUILD_EXACT_5773_SESSION_REPLICATION" if exact else "NOT_AUTHORIZED_MISSING_HISTORICAL_CADENCE_OR_PIT_AUTHORITIES",
"next_step":"BUILD_EXACT_LONG_HISTORY_REPLICATION" if exact else "AUDIT_RECONSTRUCTIBILITY_OF_MISSING_CADENCE_AND_PIT_AUTHORITIES_WITHOUT_FABRICATION",
"database_writes":False,"production_authority_effect":False}
OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps({k:out[k] for k in ("version","status","cadence_state_coverage","pit_regime_coverage","exact_5773_session_replication_authorized","disposition","next_step","production_authority_effect")},indent=2))
