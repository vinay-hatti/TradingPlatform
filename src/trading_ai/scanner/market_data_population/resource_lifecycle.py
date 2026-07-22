from __future__ import annotations

import gc
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResourceSnapshot:
    open_file_descriptors: int | None
    soft_limit: int | None
    hard_limit: int | None
    utilization_pct: float | None

    def to_dict(self) -> dict[str, int | float | None]:
        return asdict(self)


def _open_fd_count() -> int | None:
    for candidate in (Path('/dev/fd'), Path('/proc/self/fd')):
        try:
            return len(tuple(candidate.iterdir()))
        except OSError:
            continue
    return None


def snapshot_resources() -> ResourceSnapshot:
    soft = hard = None
    try:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    except (ImportError, OSError, ValueError):
        pass
    opened = _open_fd_count()
    utilization = None
    if opened is not None and soft not in (None, 0):
        utilization = opened / soft * 100.0
    return ResourceSnapshot(opened, soft, hard, utilization)


def collect_resources() -> ResourceSnapshot:
    gc.collect()
    return snapshot_resources()


def assert_fd_headroom(minimum_remaining: int = 64) -> ResourceSnapshot:
    snapshot = snapshot_resources()
    if snapshot.open_file_descriptors is not None and snapshot.soft_limit is not None:
        remaining = snapshot.soft_limit - snapshot.open_file_descriptors
        if remaining < minimum_remaining:
            raise OSError(
                24,
                f'Insufficient file-descriptor headroom: {remaining} remaining '
                f'(open={snapshot.open_file_descriptors}, soft_limit={snapshot.soft_limit})',
            )
    return snapshot
