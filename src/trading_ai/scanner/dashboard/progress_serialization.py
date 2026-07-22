from __future__ import annotations
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterable
from .progress_contracts import ProgressCheckpoint, ProgressEventType, ScanProgressEvent


def _default(value: Any) -> Any:
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, Enum): return value.value
    if is_dataclass(value): return asdict(value)
    raise TypeError(type(value).__name__)


def append_event_jsonl(path: Path, event: ScanProgressEvent) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(event, default=_default, sort_keys=True) + '\n')


def read_events_jsonl(path: Path) -> list[ScanProgressEvent]:
    events=[]
    if not path.exists(): return events
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        row=json.loads(line)
        row['event_type']=ProgressEventType(row['event_type'])
        row['occurred_at']=datetime.fromisoformat(row['occurred_at'])
        events.append(ScanProgressEvent(**row))
    return events


def write_checkpoint(path: Path, checkpoint: ProgressCheckpoint) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(checkpoint, default=_default, indent=2, sort_keys=True),encoding='utf-8')
    temp.replace(path)
