from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_ai.trend_intelligence.platform_integration import TrendPlatformIntegrationService


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build unified Milestone 52 platform context")
    parser.add_argument("--symbols", required=True)
    parser.add_argument("--output", default="reports/trend_intelligence/platform_integration_latest.json")
    args = parser.parse_args(argv)
    symbols = tuple(s.strip().upper() for s in args.symbols.split(",") if s.strip())
    service = TrendPlatformIntegrationService()
    contexts = [service.context(symbol).to_dict() for symbol in symbols]
    payload = {"market_overview": service.market_overview(symbols), "symbols": contexts}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
    print(json.dumps({"status": payload["market_overview"]["status"], "symbol_count": len(contexts), "output": str(path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
