from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_ai.paper_trading.automated_portfolio_management import (
    AutomatedPortfolioManagementPolicy,
    AutomatedPortfolioManagementService,
    render_portfolio_markdown,
    write_exposure_csv,
    write_portfolio_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Milestone 51 Phase 4 automated portfolio management."
    )
    parser.add_argument("--lifecycle-report", required=True)
    parser.add_argument("--market-data-json", required=True)
    parser.add_argument("--account-snapshot-json", required=True)
    parser.add_argument("--drawdown-pct", type=float, default=0.0)
    parser.add_argument("--execution-score", type=float, default=100.0)
    parser.add_argument(
        "--output-json",
        default="reports/m51/phase4/automated_portfolio_management.json",
    )
    parser.add_argument(
        "--output-markdown",
        default="reports/m51/phase4/automated_portfolio_management.md",
    )
    parser.add_argument(
        "--output-sector-csv",
        default="reports/m51/phase4/portfolio_sector_exposure.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    lifecycle = json.loads(
        Path(args.lifecycle_report).read_text(encoding="utf-8")
    )
    market_data = json.loads(
        Path(args.market_data_json).read_text(encoding="utf-8")
    )
    account = json.loads(
        Path(args.account_snapshot_json).read_text(encoding="utf-8")
    )
    service = AutomatedPortfolioManagementService(
        AutomatedPortfolioManagementPolicy()
    )
    result = service.execute(
        lifecycle,
        market_data,
        account,
        drawdown_pct=args.drawdown_pct,
        execution_score=args.execution_score,
    )
    payload = result.to_dict()
    json_path = write_portfolio_json(payload, args.output_json)
    markdown_path = Path(args.output_markdown)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        render_portfolio_markdown(payload),
        encoding="utf-8",
    )
    csv_path = write_exposure_csv(
        payload["exposure_by_sector"],
        args.output_sector_csv,
    )
    payload["report_paths"] = {
        "json": str(json_path),
        "markdown": str(markdown_path),
        "sector_csv": str(csv_path),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
