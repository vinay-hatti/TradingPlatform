from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np

from trading_ai.market_intelligence.contracts import MarketIntelligenceSnapshot
from trading_ai.market_intelligence.serialization import json_payload, python_scalar, to_python


def main() -> None:
    assert python_scalar(np.float64(63.56)) == 63.56
    assert isinstance(python_scalar(np.float64(63.56)), float)
    assert isinstance(python_scalar(np.int64(7)), int)
    assert isinstance(python_scalar(np.bool_(True)), bool)

    nested = {
        "confidence": np.float64(63.56),
        "components": [{"score": np.float32(47.5), "count": np.int64(4)}],
        "flags": np.array([True, False]),
    }
    normalized = to_python(nested)
    assert normalized == {
        "confidence": 63.56,
        "components": [{"score": 47.5, "count": 4}],
        "flags": [True, False],
    }
    encoded = json_payload(nested)
    assert "np.float" not in encoded
    assert json.loads(encoded)["confidence"] == 63.56

    snapshot = MarketIntelligenceSnapshot(
        snapshot_timestamp=datetime(2026, 7, 25, tzinfo=timezone.utc),
        as_of_date="2026-07-23",
        universe_name="canonical",
        sentiment={"confidence": np.float64(63.56)},
        scanner_context={"confidence": np.float64(61.2)},
    )
    payload = snapshot.to_dict()
    assert isinstance(payload["sentiment"]["confidence"], float)
    assert isinstance(payload["scanner_context"]["confidence"], float)
    json.dumps(payload, allow_nan=False)

    print("Milestone 46 NumPy serialization assertions passed.")


if __name__ == "__main__":
    main()
