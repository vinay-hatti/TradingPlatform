from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SUPPORTED_SUFFIXES = {
    ".html",
    ".json",
    ".csv",
    ".txt",
    ".log",
    ".md",
}


@dataclass(frozen=True)
class ReportFile:
    path: Path
    relative_path: str
    suffix: str
    size_bytes: int
    modified_timestamp: float


def discover_reports(
    repo_root: str | Path,
    *,
    roots: Iterable[str] = ("reports",),
    limit: int = 200,
) -> list[ReportFile]:
    repo_root = Path(repo_root).resolve()
    reports: list[ReportFile] = []

    for root_name in roots:
        root = repo_root / root_name
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue

            stat = path.stat()
            reports.append(
                ReportFile(
                    path=path,
                    relative_path=str(path.relative_to(repo_root)),
                    suffix=path.suffix.lower(),
                    size_bytes=stat.st_size,
                    modified_timestamp=stat.st_mtime,
                )
            )

    reports.sort(
        key=lambda item: item.modified_timestamp,
        reverse=True,
    )
    return reports[:limit]


def read_text_file(
    path: str | Path,
    *,
    maximum_bytes: int = 2_000_000,
) -> str:
    path = Path(path)
    if path.stat().st_size > maximum_bytes:
        return (
            f"File is {path.stat().st_size:,} bytes. "
            f"Preview is limited to {maximum_bytes:,} bytes."
        )
    return path.read_text(encoding="utf-8", errors="replace")
