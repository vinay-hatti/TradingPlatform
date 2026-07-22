from __future__ import annotations

import os
from pathlib import Path
import tempfile


class AtomicFilePublisher:
    @staticmethod
    def publish_bytes(path: str | Path, payload: bytes) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    @classmethod
    def publish_text(cls, path: str | Path, payload: str, *, encoding: str = "utf-8") -> Path:
        return cls.publish_bytes(path, payload.encode(encoding))
