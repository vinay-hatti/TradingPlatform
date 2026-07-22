from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from typing import Any

def read_json(path: Path) -> dict[str, Any]:
    if not path.exists(): return {}
    payload=json.loads(path.read_text(encoding='utf-8'))
    return payload if isinstance(payload,dict) else {'items':payload}

def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=str(path.parent))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as handle: json.dump(payload,handle,indent=2,sort_keys=True,default=str)
        os.replace(tmp,path)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise
