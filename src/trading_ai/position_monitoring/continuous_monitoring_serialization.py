from __future__ import annotations
import json
from dataclasses import asdict,is_dataclass
from datetime import date,datetime
from enum import Enum
from pathlib import Path
from typing import Any
def to_json_safe(v: Any)->Any:
    if is_dataclass(v):return to_json_safe(asdict(v))
    if isinstance(v,dict):return {str(k):to_json_safe(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,set)):return [to_json_safe(x) for x in v]
    if isinstance(v,(date,datetime)):return v.isoformat()
    if isinstance(v,Path):return str(v)
    if isinstance(v,Enum):return v.value
    return v
def dumps(v:Any,*,indent:int=2)->str:return json.dumps(to_json_safe(v),indent=indent,sort_keys=True)
