from __future__ import annotations
import json
from dataclasses import asdict,is_dataclass
from datetime import date,datetime
from enum import Enum
from pathlib import Path
from typing import Any

def to_json_safe(value: Any)->Any:
    if is_dataclass(value): return to_json_safe(asdict(value))
    if isinstance(value,dict): return {str(k):to_json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,set)): return [to_json_safe(v) for v in value]
    if isinstance(value,(date,datetime)): return value.isoformat()
    if isinstance(value,Path): return str(value)
    if isinstance(value,Enum): return value.value
    return value

def dumps(value: Any, *, indent: int=2)->str: return json.dumps(to_json_safe(value),indent=indent,sort_keys=True)
