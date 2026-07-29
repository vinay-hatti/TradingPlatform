from __future__ import annotations
import json, math, os, tempfile
from pathlib import Path
from typing import Any

def finite(value: Any) -> Any:
    if isinstance(value, dict): return {str(k): finite(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [finite(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value): return None
    return value

def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(finite(payload), f, indent=2, sort_keys=True, default=str, allow_nan=False)
            f.write('\n')
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)

def read_json(path: Path, default: Any=None) -> Any:
    try: return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError): return default

def append_history(path: Path, payload: dict, limit: int=365) -> None:
    history=read_json(path, [])
    if not isinstance(history,list): history=[]
    history.append(payload)
    write_json_atomic(path, history[-limit:])
