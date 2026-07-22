from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


def _default(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(type(value).__name__)


def write_json_atomic(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + '.tmp')
    encoded = json.dumps(payload, indent=2, sort_keys=True, default=_default)
    try:
        with temp.open('w', encoding='utf-8') as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        temp.replace(target)
    finally:
        if temp.exists():
            temp.unlink(missing_ok=True)


def write_failures_csv(path: str | Path, results) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + '.tmp')
    try:
        with temp.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=['symbol', 'status', 'failure_category', 'attempts', 'message'])
            writer.writeheader()
            for item in results:
                if item.status != 'READY':
                    writer.writerow({
                        'symbol': item.symbol,
                        'status': item.status,
                        'failure_category': getattr(item, 'failure_category', ''),
                        'attempts': item.attempts,
                        'message': item.message,
                    })
            handle.flush()
            os.fsync(handle.fileno())
        temp.replace(target)
    finally:
        if temp.exists():
            temp.unlink(missing_ok=True)


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()
