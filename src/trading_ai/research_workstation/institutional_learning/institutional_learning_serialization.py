import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

def _jsonable(v: Any):
    if hasattr(v,"isoformat"): return v.isoformat()
    if isinstance(v,dict): return {str(k):_jsonable(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [_jsonable(x) for x in v]
    return v

def institutional_learning_payload(profile): return _jsonable(asdict(profile))
def _write(payload,path):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8"); return p
def write_institutional_learning(profile,path): return _write(institutional_learning_payload(profile),path)
def write_learning_summary(profile,path): return _write(_jsonable(asdict(profile.summary)) | {"report_id":profile.report_id,"governance_status":profile.governance_status,"recommendations":list(profile.recommendations)},path)
