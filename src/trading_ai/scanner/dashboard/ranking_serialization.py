from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .ranking_contracts import RankingPage


def _default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"unsupported JSON type: {type(value).__name__}")


def ranking_page_to_dict(page: RankingPage) -> dict[str, Any]:
    return json.loads(json.dumps(page, default=_default))


def write_ranking_page(path: Path, page: RankingPage) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(page, default=_default, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
    return path
