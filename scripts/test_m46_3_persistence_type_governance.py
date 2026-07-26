from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from trading_ai.persistence_normalization import json_ready, native_params, strict_json_dumps, to_native
from trading_ai.market_intelligence.ingestion_orchestrator import PhaseRunner


def walk(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)
    else:
        yield value


def main() -> None:
    payload = {
        "float": np.float64(63.56),
        "integer": np.int64(607),
        "boolean": np.bool_(True),
        "nan": np.float64(np.nan),
        "positive_infinity": np.float64(np.inf),
        "missing": pd.NA,
        "timestamp": pd.Timestamp("2026-07-25T16:39:18Z"),
        "array": np.array([np.float64(1.5), np.nan]),
        "nested": [{"confidence": np.float32(88.25)}],
    }
    native = to_native(payload)
    assert native["float"] == 63.56 and type(native["float"]) is float
    assert native["integer"] == 607 and type(native["integer"]) is int
    assert native["boolean"] is True
    assert native["nan"] is None and native["positive_infinity"] is None and native["missing"] is None
    assert isinstance(native["timestamp"], datetime) and native["timestamp"].tzinfo is not None
    assert native["array"] == [1.5, None]
    assert all(not type(v).__module__.startswith(("numpy", "pandas")) for v in walk(native))

    params = native_params({"confidence": np.float64(63.56), "count": np.int64(3)})
    assert type(params["confidence"]) is float and type(params["count"]) is int

    encoded = strict_json_dumps(payload, sort_keys=True)
    decoded = json.loads(encoded)
    assert decoded["float"] == 63.56 and decoded["nan"] is None
    assert "NaN" not in encoded and "Infinity" not in encoded and "np.float" not in encoded

    phases = PhaseRunner(continue_on_error=False)
    reused = phases.run("existing_data", lambda: {"status": "REUSED", "rows_written": 0})
    no_new = phases.run("no_new_data", lambda: {"status": "NO_NEW_DATA", "rows_written": 0})
    assert reused.successful and no_new.successful

    service_text = Path("src/trading_ai/market_intelligence/service.py").read_text(encoding="utf-8")
    orchestrator_text = Path("src/trading_ai/market_intelligence/ingestion_orchestrator.py").read_text(encoding="utf-8")
    assert "p=to_native(snap.to_dict())" in service_text
    assert "strict_json_dumps(sm)" in service_text
    assert "json.dumps(sm)" not in service_text
    assert "metrics = to_native(" in orchestrator_text

    print("Milestone 46.3 persistence and type governance assertions passed.")


if __name__ == "__main__":
    main()
