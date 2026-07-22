from __future__ import annotations
import csv,json
from dataclasses import asdict,is_dataclass
from datetime import date
from enum import Enum
from pathlib import Path
def _v(x):
    if isinstance(x,Enum): return x.value
    if isinstance(x,date): return x.isoformat()
    if is_dataclass(x): return {k:_v(v) for k,v in asdict(x).items()}
    if isinstance(x,dict): return {str(k):_v(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [_v(v) for v in x]
    return x
def write_quality_json(profile,path):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(_v(profile),indent=2,sort_keys=True)); return p
def write_quality_csv(profile,path):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    fields=["symbol","evaluated_rows","invalid_price_rows","invalid_ohlc_rows","negative_volume_rows","zero_volume_rows","non_finite_rows","extreme_return_rows","maximum_absolute_return","quality_score","status","warnings","rejection_reasons"]
    with p.open("w",newline="",encoding="utf-8") as h:
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader()
        for x in profile.symbol_profiles:
            w.writerow({"symbol":x.symbol,"evaluated_rows":x.evaluated_rows,"invalid_price_rows":x.invalid_price_rows,"invalid_ohlc_rows":x.invalid_ohlc_rows,"negative_volume_rows":x.negative_volume_rows,"zero_volume_rows":x.zero_volume_rows,"non_finite_rows":x.non_finite_rows,"extreme_return_rows":x.extreme_return_rows,"maximum_absolute_return":x.maximum_absolute_return,"quality_score":x.quality_score,"status":x.status.value,"warnings":" | ".join(x.warnings),"rejection_reasons":" | ".join(x.rejection_reasons)})
    return p
