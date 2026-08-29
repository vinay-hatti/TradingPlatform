#!/usr/bin/env python3
import argparse,json
from collections import Counter,defaultdict
from pathlib import Path
from statistics import mean

VERSION="CYCLICAL-SEASONALITY-CANDIDATE-REFINEMENT-STABILITY-AUDIT-1.0"
SOURCE="CYCLICAL-SEASONALITY-FOLD-NATIVE-MATCHED-CONTROL-SHADOW-CERT-1.0"
FULL=(2024,2025); FLOOR={20:.25,60:.50}

def bh(pairs):
 x=sorted([(k,float(p)) for k,p in pairs if p is not None],key=lambda z:(z[1],z[0]));m=len(x)
 if not m:return {}
 v=[min(1,p*m/i) for i,(_,p) in enumerate(x,1)]
 for i in range(m-2,-1,-1):v[i]=min(v[i],v[i+1])
 return {x[i][0]:v[i] for i in range(m)}

def fmap(c):return {int(x["holdout_year"]):x for x in c.get("folds",[])}
def m(f,k):return (f.get("matched") or {}).get(k)
def rs(f):return set((f.get("verdict") or {}).get("reasons") or [])

def concentration(fs):
 sy=[]
 for f in fs:
  for k in (f.get("matched") or {}).get("candidate_observation_keys",[]):
   p=str(k).split("|")
   if len(p)>1:sy.append(p[1])
 if not sy:return {"observations":0,"symbols":0,"top_symbol_share_pct":None,"top_10_symbol_share_pct":None}
 c=Counter(sy);n=len(sy);v=sorted(c.values(),reverse=True)
 return {"observations":n,"symbols":len(c),"top_symbol_share_pct":100*v[0]/n,"top_10_symbol_share_pct":100*sum(v[:10])/n}

def classify(c):
 fm=fmap(c);fs=[fm.get(y) for y in FULL];h=int(c["horizon"])
 if any(f is None for f in fs):return "INSUFFICIENT_FULL_YEAR_EVIDENCE",["MISSING_FULL_YEAR_FOLD"]
 if all(f["verdict"]["passed"] for f in fs):return "STRICT_CERTIFICATION_CANDIDATE",[]
 near=True;why=[]
 for f in fs:
  if (m(f,"matched_observations") or 0)<100:near=False
  if (m(f,"matched_coverage_pct") or 0)<80:near=False
  if (m(f,"candidate_thesis_return_avg_pct") or -999)<=0:near=False
  if (m(f,"matched_excess_thesis_return_avg_pct") or -999)<FLOOR[h]:near=False
  q=m(f,"matched_excess_fdr_qvalue")
  if q is None or q>.20:near=False
  why += list(rs(f))
 if near:return "NEAR_CERTIFICATION_FDR_ONLY",sorted(set(why))
 if any((m(f,"matched_observations") or 0)<100 or (m(f,"matched_coverage_pct") or 0)<80 for f in fs):
  return "INSUFFICIENT_CONTROL_COVERAGE",sorted(set().union(*(rs(f) for f in fs)))
 ex=[m(f,"matched_excess_thesis_return_avg_pct") for f in fs]
 if any(x is not None and x>=FLOOR[h] for x in ex) and not all(x is not None and x>=FLOOR[h] for x in ex):
  return "CROSS_YEAR_UNSTABLE",sorted(set().union(*(rs(f) for f in fs)))
 return "STATISTICALLY_UNSUPPORTED",sorted(set().union(*(rs(f) for f in fs)))

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--input",default="reports/cyclical_seasonality/cyclical_seasonality_fold_native_shadow_certification.json");ap.add_argument("--output",default="reports/cyclical_seasonality/cyclical_seasonality_candidate_refinement_stability_audit.json");a=ap.parse_args()
 inp,out=Path(a.input),Path(a.output)
 if not inp.exists():raise SystemExit(f"Missing predecessor: {inp}")
 src=json.loads(inp.read_text())
 if src.get("version")!=SOURCE:raise SystemExit(f"Expected {SOURCE}")
 g=src["governance"]
 if not(g["production_authority_effect"] is False and g["database_writes"] is False and g["automatic_shadow_activation"] is False):raise SystemExit("Predecessor governance not fail-closed")
 rows=[];source={}
 for c in src.get("certifications",[]):
  source[c["candidate_id"]]=c;cl,why=classify(c);fm=fmap(c);fs=[fm[y] for y in FULL if y in fm]
  rows.append({"candidate_id":c["candidate_id"],"factor_family":c["factor_family"],"factor":c["factor"],"state":c["state"],"direction":c["direction"],"horizon":int(c["horizon"]),"classification":cl,"failure_reasons":why,
   "full_year":{"matched_excess_pct":[m(f,"matched_excess_thesis_return_avg_pct") for f in fs],"fdr_q":[m(f,"matched_excess_fdr_qvalue") for f in fs],"thesis_return_pct":[m(f,"candidate_thesis_return_avg_pct") for f in fs],"coverage_pct":[m(f,"matched_coverage_pct") for f in fs],"matched_n":[m(f,"matched_observations") for f in fs]},
   "symbol_membership_concentration":concentration(fs)})
 fam=defaultdict(list)
 for r in rows:
  fm=fmap(source[r["candidate_id"]]);ps=[m(fm[y],"matched_excess_pvalue_approx") for y in FULL if y in fm]
  p=max(ps) if ps and all(x is not None for x in ps) else None;r["worst_full_year_pvalue_approx"]=p;fam[r["factor_family"]].append((r["candidate_id"],p))
 within={k:bh(v) for k,v in fam.items()};fmin=[(k,min(p for _,p in v if p is not None)) for k,v in fam.items() if any(p is not None for _,p in v)];fq=bh(fmin)
 for r in rows:r["hierarchical_testing_diagnostic"]={"family_qvalue":fq.get(r["factor_family"]),"within_family_candidate_qvalue":within[r["factor_family"]].get(r["candidate_id"]),"certification_effect":False}
 order={"NEAR_CERTIFICATION_FDR_ONLY":0,"CROSS_YEAR_UNSTABLE":1,"INSUFFICIENT_CONTROL_COVERAGE":2,"STATISTICALLY_UNSUPPORTED":3,"INSUFFICIENT_FULL_YEAR_EVIDENCE":4,"STRICT_CERTIFICATION_CANDIDATE":5}
 rows.sort(key=lambda r:(order.get(r["classification"],99),r["candidate_id"]))
 counts=Counter(r["classification"] for r in rows);near=Counter(r["factor_family"] for r in rows if r["classification"]=="NEAR_CERTIFICATION_FDR_ONLY")
 result={"version":VERSION,"status":"READY","governance":{"research_only":True,"read_only_artifact_analysis":True,"database_writes":False,"database_migrations":False,"production_authority_effect":False,"production_model_mutation":False,"production_threshold_change":False,"production_weight_change":False,"production_decision_change":False,"automatic_shadow_activation":False,"automatic_champion_promotion":False,"certification_thresholds_relaxed":False},
 "lineage":{"input":str(inp),"input_version":src["version"]},"methodology":{"purpose":"Refine zero-survivor result without weakening certification gates","full_years":[2024,2025],"near_certification_contract":"Both full years satisfy N>=100, coverage>=80%, positive thesis return and existing horizon effect floor; only FDR may fail and q must be <=0.20","hierarchical_testing":"Diagnostic only; worst full-year p, BH within family and BH across family minima; cannot retroactively certify","symbol_concentration":"Membership concentration from matched candidate observation keys; not return-contribution attribution","prohibited":"No post-hoc relaxation of q<=0.10, coverage>=80%, N>=100, or effect floors"},
 "summary":{"candidates":len(rows),"classifications":dict(sorted(counts.items())),"near_certification_by_family":dict(sorted(near.items())),"production_champion_change":False,"shadow_activation":False},"candidates":rows,
 "disposition":{"shadow_or_production_now":"PROHIBITED","recommended_next_gate":"TARGETED_ROBUSTNESS_FOR_NEAR_CERTIFICATION_ONLY" if counts.get("NEAR_CERTIFICATION_FDR_ONLY",0)>0 else "STOP_OR_COLLECT_MORE_FORWARD_DATA","do_not_relax_existing_certification_gates":True}}
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps({"status":"READY","version":VERSION,"output":str(out),"summary":result["summary"],"disposition":result["disposition"]},indent=2))
if __name__=="__main__":main()
