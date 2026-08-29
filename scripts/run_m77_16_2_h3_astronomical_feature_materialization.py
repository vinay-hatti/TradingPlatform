#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from pathlib import Path

from trading_ai.historical_underlying_replay.mundane_market_house_features import (
    RASHI, angular_distance, derive_reference_chart, rashi_index
)

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config/m77/m77_16_2_h3_feature_materialization.json"
CONFIRM="MATERIALIZE_M77_16_2_H3_ASTRONOMICAL_FEATURES"

FIELDS=[
"date","rahu_sidereal_deg","ketu_sidereal_deg",
"reference_ascendant_sidereal_deg","reference_ascendant_rashi",
"fifth_house_rashi","eleventh_house_rashi","fifth_house_lord","eleventh_house_lord",
"fifth_house_lord_sidereal_deg","eleventh_house_lord_sidereal_deg",
"rahu_in_5th_house","ketu_in_5th_house","rahu_in_11th_house","ketu_in_11th_house",
"rahu_conjunct_5th_lord","ketu_conjunct_5th_lord","rahu_conjunct_11th_lord","ketu_conjunct_11th_lord",
"rahu_5th_lord_separation_deg","ketu_5th_lord_separation_deg","rahu_11th_lord_separation_deg","ketu_11th_lord_separation_deg"
]

def load_csv(p):
    with Path(p).open() as f:return list(csv.DictReader(f))

def write_csv_atomic(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+".tmp")
    with t.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    t.replace(p)

def write_json_atomic(p,x):
    p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(x,indent=2,default=str)+"\n"); json.loads(t.read_text()); t.replace(p)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("preflight","materialize","parity"))
    ap.add_argument("--confirm")
    a=ap.parse_args()

    cfg=json.loads(CFG.read_text())
    cert=ROOT/cfg["required_market_chart_certification"]
    if not cert.exists(): raise SystemExit("M77.16.2 blocked: M77.16.1 certification missing")
    cx=json.loads(cert.read_text())
    if not cx.get("certified_for_h3_feature_materialization"):
        raise SystemExit("M77.16.2 blocked: M77.16.1 market-chart authority not certified")

    chart=derive_reference_chart(cfg)
    lords=cx["market_chart_authority"]["lordship_scheme"]
    fifth_lord=lords[chart["fifth_house_rashi"].replace("MESHA","ARIES").replace("VRISHABHA","TAURUS").replace("MITHUNA","GEMINI").replace("KARKA","CANCER").replace("SIMHA","LEO").replace("KANYA","VIRGO").replace("TULA","LIBRA").replace("VRISCHIKA","SCORPIO").replace("DHANU","SAGITTARIUS").replace("MAKARA","CAPRICORN").replace("KUMBHA","AQUARIUS").replace("MEENA","PISCES")]
    eleventh_lord=lords[chart["eleventh_house_rashi"].replace("MESHA","ARIES").replace("VRISHABHA","TAURUS").replace("MITHUNA","GEMINI").replace("KARKA","CANCER").replace("SIMHA","LEO").replace("KANYA","VIRGO").replace("TULA","LIBRA").replace("VRISCHIKA","SCORPIO").replace("DHANU","SAGITTARIUS").replace("MAKARA","CAPRICORN").replace("KUMBHA","AQUARIUS").replace("MEENA","PISCES")]

    if a.mode=="preflight":
        print(json.dumps({
            "version":cfg["version"],"status":"READY","confirmation_required":CONFIRM,
            "reference_chart":chart,"fifth_house_lord":fifth_lord,"eleventh_house_lord":eleventh_lord,
            "feature_definition":cfg["feature_definition"],"production_authority_effect":False
        },indent=2)); return

    if a.mode=="parity":
        ay=chart["lahiri_ayanamsha_deg"]
        bench=cfg["frozen_external_benchmarks"]["lahiri_ayanamsha_1792_05_17_deg"]
        gates={
            "lahiri_external_benchmark_parity":abs(ay-bench)<=cfg["frozen_external_benchmarks"]["lahiri_tolerance_deg"],
            "dual_ascendant_formula_parity":chart["ascendant_formula_parity_error_deg"]<=1e-9,
            "whole_sign_5th_mapping":chart["fifth_house_rashi_index"]==(chart["ascendant_rashi_index"]+4)%12,
            "whole_sign_11th_mapping":chart["eleventh_house_rashi_index"]==(chart["ascendant_rashi_index"]+10)%12,
        }
        print(json.dumps({
            "version":cfg["version"],"status":"READY","reference_chart":chart,
            "fifth_house_lord":fifth_lord,"eleventh_house_lord":eleventh_lord,
            "gates":gates,"parity_pass":all(gates.values()),"production_authority_effect":False
        },indent=2)); return

    if a.confirm!=CONFIRM: raise SystemExit(f"confirmation required: {CONFIRM}")

    rows=load_csv(ROOT/cfg["source_graha_registry"])
    orb=float(cfg["feature_definition"]["conjunction_orb_deg"])
    out=[]
    node_opp_max=0.0

    for r in rows:
        rahu=float(r["rahu_sidereal_deg"]); ketu=float(r["ketu_sidereal_deg"])
        fl=float(r[f"{fifth_lord.lower()}_sidereal_deg"])
        el=float(r[f"{eleventh_lord.lower()}_sidereal_deg"])
        node_opp=abs(angular_distance(rahu,ketu)-180.0); node_opp_max=max(node_opp_max,node_opp)

        r5=angular_distance(rahu,fl); k5=angular_distance(ketu,fl)
        r11=angular_distance(rahu,el); k11=angular_distance(ketu,el)
        out.append({
            "date":r["date"],"rahu_sidereal_deg":rahu,"ketu_sidereal_deg":ketu,
            "reference_ascendant_sidereal_deg":chart["sidereal_ascendant_deg"],
            "reference_ascendant_rashi":chart["ascendant_rashi"],
            "fifth_house_rashi":chart["fifth_house_rashi"],"eleventh_house_rashi":chart["eleventh_house_rashi"],
            "fifth_house_lord":fifth_lord,"eleventh_house_lord":eleventh_lord,
            "fifth_house_lord_sidereal_deg":fl,"eleventh_house_lord_sidereal_deg":el,
            "rahu_in_5th_house":rashi_index(rahu)==chart["fifth_house_rashi_index"],
            "ketu_in_5th_house":rashi_index(ketu)==chart["fifth_house_rashi_index"],
            "rahu_in_11th_house":rashi_index(rahu)==chart["eleventh_house_rashi_index"],
            "ketu_in_11th_house":rashi_index(ketu)==chart["eleventh_house_rashi_index"],
            "rahu_conjunct_5th_lord":r5<=orb,"ketu_conjunct_5th_lord":k5<=orb,
            "rahu_conjunct_11th_lord":r11<=orb,"ketu_conjunct_11th_lord":k11<=orb,
            "rahu_5th_lord_separation_deg":r5,"ketu_5th_lord_separation_deg":k5,
            "rahu_11th_lord_separation_deg":r11,"ketu_11th_lord_separation_deg":k11,
        })

    op=ROOT/cfg["output_registry"]; write_csv_atomic(op,out)
    counts={k:sum(1 for r in out if r[k] in (True,"True",1,"1")) for k in (
        "rahu_in_5th_house","ketu_in_5th_house","rahu_in_11th_house","ketu_in_11th_house",
        "rahu_conjunct_5th_lord","ketu_conjunct_5th_lord","rahu_conjunct_11th_lord","ketu_conjunct_11th_lord"
    )}
    meta={
        "version":cfg["version"],"status":"READY","rows":len(out),
        "first_date":out[0]["date"] if out else None,"last_date":out[-1]["date"] if out else None,
        "reference_chart":chart,"fifth_house_lord":fifth_lord,"eleventh_house_lord":eleventh_lord,
        "feature_counts":counts,"max_node_opposition_error_deg":node_opp_max,
        "financial_outcomes_present":False,
        "gates":{
            "rows_cover_2000_2040":len(out)>=14900,
            "node_opposition_invariant":node_opp_max<=1e-6,
            "financial_outcomes_absent":True,
            "factor_combinations_absent":True
        },
        "certified_for_h3_financial_study":len(out)>=14900 and node_opp_max<=1e-6,
        "next_step":"BUILD_M77_16_3_H3_LONG_HISTORY_FINANCIAL_STUDY" if len(out)>=14900 and node_opp_max<=1e-6 else "REVIEW_M77_16_2_FEATURE_PARITY",
        "database_writes":False,"production_authority_effect":False
    }
    write_json_atomic(ROOT/cfg["output_metadata"],meta)
    print(json.dumps(meta,indent=2))

if __name__=="__main__": main()
