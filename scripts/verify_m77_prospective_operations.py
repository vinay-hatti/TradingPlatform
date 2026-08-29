from __future__ import annotations
import json, subprocess
from pathlib import Path

ROOT=Path("/Users/vinay.hatti/TradingPlatform")
TRACKS=[
    ("PSVE","data/positive_selection_shadow"),
    ("MGE","data/management_geometry_shadow"),
    ("CQMI","data/candidate_quality_management_interaction_shadow"),
    ("CPRE","data/cross_sectional_capital_priority_shadow"),
    ("CACA","data/capacity_aware_capital_allocation_shadow"),
]

def main():
    rows=[];problems=[]
    for label,raw in TRACKS:
        base=ROOT/raw
        protocol=base/"FROZEN_PROSPECTIVE_PROTOCOL.json"
        snaps=sorted((base/"snapshots").glob("*.json")) if (base/"snapshots").exists() else []
        matured=sorted((base/"matured").glob("*.json")) if (base/"matured").exists() else []
        row={
            "track":label,
            "protocol_frozen":protocol.exists(),
            "snapshot_count":len(snaps),
            "latest_snapshot":snaps[-1].stem if snaps else None,
            "matured_snapshot_count":len(matured),
        }
        rows.append(row)
        if not protocol.exists(): problems.append(f"{label}:protocol_missing")
        if not snaps: problems.append(f"{label}:no_snapshots")

    script=ROOT/"scripts/m77_forward_shadow/run_combined_forward_shadow.sh"
    syntax_ok=subprocess.run(["/bin/bash","-n",str(script)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
    if not syntax_ok: problems.append("combined_script:syntax_error")

    result={
        "status":"PASS" if not problems else "FAIL",
        "tracks":rows,
        "combined_script_syntax_ok":syntax_ok,
        "problems":problems,
        "production_authority_effect":False,
    }
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result["status"]=="PASS" else 1

if __name__=="__main__":
    raise SystemExit(main())
