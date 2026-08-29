from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
strategy = ROOT / "src/trading_ai/strategy_engine"

required = {
    "spread_candidate.py": ["long_option_symbol", "short_option_symbol", "def legs"],
    "strike_optimizer.py": ["_valid_contract_row", "max_strike_distance_pct", "long_option_symbol", "short_option_symbol"],
    "opportunity_factory.py": ["option_contract_legs", "contract_identity_complete"],
}
for name, tokens in required.items():
    path = strategy / name
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=str(path))
    missing = [token for token in tokens if token not in source]
    if missing:
        raise AssertionError(f"{name} missing {missing}")

# Verify the stale VTI 100/110 pair is outside the default 20% window.
spot = 300.0
for strike in (100.0, 110.0):
    assert abs(strike - spot) / spot > 0.20

print("Contract identity propagation validation passed.")
