import json
from dataclasses import asdict, is_dataclass
from pathlib import Path

def _j(v):
    if is_dataclass(v):
        return {k: _j(x) for k, x in asdict(v).items()}
    if isinstance(v, dict):
        return {str(k): _j(x) for k, x in v.items()}
    if isinstance(v, (tuple, list)):
        return [_j(x) for x in v]
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v

def institutional_scanner_payload(*, candidates, run):
    return {"run": _j(run), "candidates": [_j(c) for c in candidates]}

def write_institutional_scanner_report(*, candidates, run, output_file):
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = institutional_scanner_payload(candidates=candidates, run=run)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
