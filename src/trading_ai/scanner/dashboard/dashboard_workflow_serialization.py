from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .dashboard_workflow_profile import (
    DashboardWorkflowReport,
)


def write_dashboard_workflow_report_atomic(
    path: Path,
    report: DashboardWorkflowReport,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                report.to_dict(),
                handle,
                indent=2,
                default=str,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        temp_path = Path(temp_name)
        if temp_path.exists():
            temp_path.unlink()
    return path
