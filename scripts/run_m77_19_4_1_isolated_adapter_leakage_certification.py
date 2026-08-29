#!/usr/bin/env python3
import ast,hashlib,json
from datetime import date,timedelta
from pathlib import Path
from trading_ai.historical_underlying_replay.m77_19_4_isolated_adapters import snapshot,daily_dates,monthly_dates
ROOT=Path(__file__).resolve().parents[1];CFG=ROOT/"config/m77/m77_19_4_1_adapter_leakage_certification.json";OUT=ROOT/"reports/m77/m77_19_4_1_isolated_adapter_leakage_certification.json"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def synth():
 ds=[];d=date(2020,1,1)
 while len(ds)<330:
  if d.weekday()<5:ds.append(d)
  d+=timedelta(days=1)
 rows=[]
 for i,x in enumerate(ds):rows += [("SPY",x,100+i*.1+((i%11)-5)*.03),("AAA",x,50+i*.06+((i%7)-3)*.02),("BBB",x,80-i*.015+((i%9)-4)*.02)]
 return ds,rows
def main():
 c=json.loads(CFG.read_text());parity={k:{"expected":v,"actual":sha(ROOT/k) if (ROOT/k).exists() else None} for k,v in c["frozen_sha256"].items()}
 for v in parity.values():v["pass"]=v["actual"]==v["expected"]
 ds,rows=synth();a=ds[300];base=snapshot(rows,a);repeat=snapshot(rows,a);mut=rows+[("SPY",ds[320],999999),("AAA",ds[320],.01),("BBB",ds[320],999999)];changed=snapshot(mut,a)
 reg=(ROOT/"src/trading_ai/historical_underlying_replay/regime.py").read_text();svc=(ROOT/"src/trading_ai/historical_underlying_replay/service.py").read_text().replace(" ","")
 adap=ROOT/"src/trading_ai/historical_underlying_replay/m77_19_4_isolated_adapters.py";tree=ast.parse(adap.read_text());bad=[]
 for n in ast.walk(tree):
  if isinstance(n,ast.ImportFrom) and (n.module or "").startswith(("sqlalchemy","trading_ai.database")):bad.append(n.module)
  if isinstance(n,ast.Import):
   bad += [x.name for x in n.names if x.name.startswith(("sqlalchemy","trading_ai.database"))]
 gates={"source_sha256_parity":all(x["pass"] for x in parity.values()),"synthetic_deterministic_repeat":base==repeat,"synthetic_future_mutation_invariant":base==changed,"source_regime_sql_bounded_date_le_end":"WHERE date <= :end" in reg,"source_regime_uses_max_replay_date":"_load_price_history(max(replay_dates))" in reg,"source_service_history_ends_at_as_of":"history=rows[max(0,pos-749):pos+1]" in svc,"source_service_future_begins_after_as_of":"future=rows[pos+1:pos+61]" in svc,"adapter_has_no_db_imports":not bad}
 dd=daily_dates(ds,ds[252],ds[300]);md=monthly_dates(ds,ds[252],ds[300]);gates["daily_adapter_range_bounded"]=all(ds[252]<=x<=ds[300] for x in dd);gates["monthly_adapter_range_bounded"]=all(ds[252]<=x<=ds[300] for x in md)
 certified=all(gates.values())
 out={"version":c["version"],"status":"READY","source_parity":parity,"gates":gates,"synthetic_baseline":base,"adapter_certified_for_isolated_historical_replay":certified,"production_historical_replay_authorized":False,"remaining_blocker":"ORIGINAL_601_SYMBOL_LONG_HISTORY_SOURCE_DATA_MISSING","next_step":"BUILD_M77_19_5_ORIGINAL_601_SYMBOL_LONG_HISTORY_SOURCE_AUTHORITY" if certified else "REVIEW_M77_19_4_1_CERTIFICATION_FAILURES","database_writes":False,"production_authority_effect":False}
 OUT.parent.mkdir(parents=True,exist_ok=True)
 tmp=OUT.with_suffix(OUT.suffix+".tmp")
 tmp.write_text(json.dumps(out,indent=2)+"\n")
 json.loads(tmp.read_text())
 tmp.replace(OUT)
 print(json.dumps(out,indent=2))
if __name__=="__main__":main()
