from __future__ import annotations

import json
from pathlib import Path

from .profile import PublishedStateResolution


def write_resolution_json(path: str | Path, result: PublishedStateResolution) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True, default=str) + "\n")
    temporary.replace(target)
    return target
