from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from trading_ai.research_workstation.phase3_pipeline import (
    Phase3PipelineEngine,
)


def demo_manifest(
    *,
    trade_id: str,
    symbol: str,
    strategy_name: str,
) -> dict[str, Any]:
    as_of = date.today()
    expiration = as_of + timedelta(days=33)

    return {
        "trade": {
            "trade_id": trade_id,
            "symbol": symbol,
            "sector": "TECHNOLOGY",
            "strategy_name": strategy_name,
            "direction": "BULLISH",
            "requested_contracts": 2,
            "maximum_profit_per_contract": 400.0,
            "maximum_loss_per_contract": 320.0,
            "probability_of_profit": 0.72,
            "breakeven_points": [198.20],
            "quantity_ratios": [1, 1],
            "legs": [
                {
                    "expiration": expiration.isoformat(),
                    "option_type": "PUT",
                    "side": "SHORT",
                    "strike": 200.0,
                    "bid": 2.45,
                    "ask": 2.55,
                    "mark": 2.50,
                    "open_interest": 8500,
                    "volume": 1400,
                    "delta": -0.28,
                    "gamma": 0.04,
                    "theta": -0.08,
                    "vega": 0.12
                },
                {
                    "expiration": expiration.isoformat(),
                    "option_type": "PUT",
                    "side": "LONG",
                    "strike": 195.0,
                    "bid": 0.65,
                    "ask": 0.75,
                    "mark": 0.70,
                    "open_interest": 6200,
                    "volume": 900,
                    "delta": -0.16,
                    "gamma": 0.03,
                    "theta": -0.05,
                    "vega": 0.09
                }
            ]
        },
        "account": {
            "account_equity": 100000.0
        },
        "portfolio_planning": {
            "candidate_id": f"{trade_id}-CANDIDATE",
            "maximum_contracts": 2,
            "expected_return_pct": 0.10,
            "annualized_volatility_pct": 0.24,
            "expected_shortfall_per_contract": 160.0,
            "liquidity_score": 92.0,
            "greeks_per_contract": {
                "delta": 12.0,
                "gamma": -1.0,
                "theta": 3.0,
                "vega": -4.0
            },
            "correlations": []
        },
        "lifecycle": {
            "as_of_date": as_of.isoformat(),
            "confidence": 0.82,
            "event_date": None
        },
        "governance": {
            "broker_ready": True,
            "compliance_cleared": True,
            "event_risk_present": False,
            "override_requested": False,
            "override_approved": False,
            "override_scope": []
        }
    }


def write_template(path: Path) -> None:
    payload = demo_manifest(
        trade_id="TRADE-001",
        symbol="AAPL",
        strategy_name="BULL_PUT_SPREAD",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the complete Milestone 34 Phase 3 workflow and "
            "generate every intermediate and final report."
        )
    )
    parser.add_argument("--input-json")
    parser.add_argument("--trade-id", default="TRADE-001")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument(
        "--strategy-name",
        "--strategy",
        dest="strategy_name",
        default="BULL_PUT_SPREAD",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/m34/phase3",
    )
    parser.add_argument(
        "--write-template",
        help=(
            "Write an editable Phase 3 input manifest and exit."
        ),
    )
    args = parser.parse_args()

    if args.write_template:
        template_path = Path(args.write_template)
        write_template(template_path)
        print(f"Phase 3 input template: {template_path}")
        return

    if args.input_json:
        input_path = Path(args.input_json)
        if not input_path.exists():
            raise FileNotFoundError(
                f"Phase 3 input manifest not found: {input_path}"
            )
        manifest = json.loads(
            input_path.read_text(encoding="utf-8")
        )
        mode = f"manifest: {input_path}"
    else:
        manifest = demo_manifest(
            trade_id=args.trade_id,
            symbol=args.symbol.upper(),
            strategy_name=args.strategy_name.upper(),
        )
        mode = "deterministic demo manifest"

    result = Phase3PipelineEngine().run(
        manifest=manifest,
        output_directory=args.output_dir,
    )

    print("Milestone 34 Phase 3 pipeline completed.")
    print(f"Input mode: {mode}")
    print(f"Trade construction: {result.trade_construction_report}")
    print(f"Portfolio allocation: {result.portfolio_allocation_report}")
    print(f"Trade lifecycle: {result.trade_lifecycle_report}")
    print(f"Pre-trade governance: {result.pretrade_governance_report}")
    print(f"Dashboard JSON: {result.dashboard_json_report}")
    print(f"Dashboard HTML: {result.dashboard_html_report}")
    print(f"Pipeline report: {result.pipeline_report}")
    print(f"Overall status: {result.overall_status}")
    print(f"Approval status: {result.approval_status}")
    print(f"Execution allowed: {result.execution_allowed}")


if __name__ == "__main__":
    main()
