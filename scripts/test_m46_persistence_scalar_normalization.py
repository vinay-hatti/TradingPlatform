from __future__ import annotations

import json
from datetime import date, datetime, timezone

import numpy as np

from trading_ai.market_intelligence.service import _json_payload, _python_scalar


def assert_native(value):
    if isinstance(value, dict):
        for item in value.values():
            assert_native(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            assert_native(item)
        return
    assert not type(value).__module__.startswith("numpy"), type(value)


def main() -> None:
    payload = {
        "float": np.float64(47.5),
        "integer": np.int64(12),
        "boolean": np.bool_(True),
        "nested": [np.float32(1.25), {"value": np.int32(4)}],
        "date": date(2026, 7, 23),
        "timestamp": datetime(2026, 7, 23, 15, 30, tzinfo=timezone.utc),
    }

    normalized = _python_scalar(payload)
    assert_native(normalized)
    assert normalized["float"] == 47.5
    assert normalized["integer"] == 12
    assert normalized["boolean"] is True

    encoded = _json_payload(payload)
    decoded = json.loads(encoded)
    assert decoded["float"] == 47.5
    assert decoded["integer"] == 12
    assert decoded["boolean"] is True
    assert "np.float" not in encoded

    print("Milestone 46 persistence scalar normalization assertions passed.")


if __name__ == "__main__":
    main()
