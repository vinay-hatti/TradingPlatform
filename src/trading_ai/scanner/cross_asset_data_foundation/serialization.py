import json, os
from dataclasses import asdict
from datetime import date, datetime
from enum import Enum
from pathlib import Path

def _default(value):
    if isinstance(value, (date, datetime)): return value.isoformat()
    if isinstance(value, Enum): return value.value
    raise TypeError(type(value).__name__)

def write_jsonl_atomic(path, records):
    output = Path(path); output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as h:
        for record in records:
            h.write(json.dumps(asdict(record), sort_keys=True, default=_default) + "\n")
    os.replace(temp, output); return output

def write_json_atomic(path, value):
    output = Path(path); output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    payload = asdict(value) if hasattr(value, "__dataclass_fields__") else value
    with temp.open("w", encoding="utf-8") as h:
        json.dump(payload, h, indent=2, sort_keys=True, default=_default); h.write("\n")
    os.replace(temp, output); return output
