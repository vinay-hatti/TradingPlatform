from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_market_ingestion.py"

# Isolate symbol-resolution tests from downloader dependencies.
market_module = types.ModuleType("trading_ai.market")
downloader_module = types.ModuleType("trading_ai.market.downloader")
downloader_module.MarketDownloader = object
sys.modules.setdefault("trading_ai", types.ModuleType("trading_ai"))
sys.modules["trading_ai.market"] = market_module
sys.modules["trading_ai.market.downloader"] = downloader_module

spec = importlib.util.spec_from_file_location("run_market_ingestion", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)

    canonical = root / "universe.csv"
    with canonical.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["symbol", "active"])
        writer.writeheader()
        writer.writerows(
            [
                {"symbol": "AAPL", "active": "True"},
                {"symbol": "MSFT", "active": "True"},
                {"symbol": "OLD", "active": "False"},
                {"symbol": "AAPL", "active": "True"},
            ]
        )

    assert module.resolve_symbols(None, None, canonical) == ("AAPL", "MSFT")
    assert module.resolve_symbols(" nvda, aapl,NVDA ", None, canonical) == (
        "NVDA",
        "AAPL",
    )

    text_file = root / "symbols.txt"
    text_file.write_text("# custom list\nTSLA\nAMD, AMZN\nTSLA\n", encoding="utf-8")
    assert module.resolve_symbols(None, str(text_file), canonical) == (
        "TSLA",
        "AMD",
        "AMZN",
    )

print("Milestone 43 market-ingestion symbol-source assertions passed.")
