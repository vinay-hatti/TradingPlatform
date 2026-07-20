from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from trading_ai.research_workstation.research_cases import (
    ResearchCaseEngine,
    write_research_case_report,
)


def demo_research_case(
    *,
    case_id: str,
    symbol: str,
    strategy_name: str,
) -> dict[str, Any]:
    today = date.today()
    observed_at = datetime.now(timezone.utc).isoformat()

    return {
        "case_id": case_id,
        "symbol": symbol,
        "strategy_name": strategy_name,
        "title": (
            f"{symbol} {strategy_name} institutional research case"
        ),
        "primary_thesis": (
            "Constructive market structure, controlled downside, "
            "and favorable scenario-weighted return support a "
            "defined-risk options position."
        ),
        "time_horizon": "30-45 DAYS",
        "review_date": (
            today + timedelta(days=7)
        ).isoformat(),
        "confidence_score": 0.82,
        "scenarios": [
            {
                "scenario_id": "BASE",
                "name": "Base Case",
                "scenario_type": "BASE",
                "probability": 0.50,
                "expected_return_pct": 0.10,
                "expected_volatility_pct": 0.24,
                "expected_drawdown_pct": 0.05,
                "expected_holding_days": 21,
                "thesis": (
                    "Price remains above primary support."
                ),
                "catalysts": [
                    "Stable earnings expectations"
                ],
                "risks": [
                    "Broad market weakness"
                ],
                "invalidation_conditions": [
                    "Daily close below primary support"
                ],
                "recommended_action": "ENTER"
            },
            {
                "scenario_id": "BULL",
                "name": "Bull Case",
                "scenario_type": "BULL",
                "probability": 0.25,
                "expected_return_pct": 0.22,
                "expected_volatility_pct": 0.28,
                "expected_drawdown_pct": 0.03,
                "expected_holding_days": 14,
                "thesis": (
                    "Upside momentum accelerates."
                ),
                "catalysts": [
                    "Positive guidance"
                ],
                "risks": [
                    "Volatility compression"
                ],
                "invalidation_conditions": [
                    "Momentum confirmation fails"
                ],
                "recommended_action": "ENTER"
            },
            {
                "scenario_id": "BEAR",
                "name": "Bear Case",
                "scenario_type": "BEAR",
                "probability": 0.25,
                "expected_return_pct": -0.12,
                "expected_volatility_pct": 0.36,
                "expected_drawdown_pct": 0.18,
                "expected_holding_days": 10,
                "thesis": (
                    "Support fails after a macro shock."
                ),
                "catalysts": [
                    "Risk-off repricing"
                ],
                "risks": [
                    "Gap risk"
                ],
                "invalidation_conditions": [
                    "Price reclaims failed support"
                ],
                "recommended_action": "AVOID"
            }
        ],
        "evidence": [
            {
                "evidence_id": "E-001",
                "category": "TECHNICAL",
                "description": (
                    "Price remains above trend support."
                ),
                "source": "FeaturePipeline",
                "observed_at": observed_at,
                "reliability_score": 0.85,
                "supports_thesis": True,
                "notes": (
                    "Deterministic demo evidence; replace with "
                    "production research data."
                )
            }
        ],
        "assumptions": [
            {
                "assumption_id": "A-001",
                "description": (
                    "No material deterioration in earnings outlook."
                ),
                "importance": "HIGH",
                "confidence": 0.75,
                "validation_method": (
                    "Monitor earnings revisions and guidance."
                ),
                "invalidation_condition": (
                    "Consensus earnings estimate falls materially."
                )
            }
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the Milestone 34 Phase 4 research-case report."
        )
    )
    parser.add_argument("--input-json")
    parser.add_argument("--case-id", default="CASE-001")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument(
        "--strategy-name",
        "--strategy",
        dest="strategy_name",
        default="BULL_PUT_SPREAD",
    )
    parser.add_argument(
        "--output",
        default="reports/m34/phase4/research_case.json",
    )
    parser.add_argument(
        "--write-template",
        help="Write an editable research-case manifest and exit.",
    )
    args = parser.parse_args()

    if args.write_template:
        path = Path(args.write_template)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = demo_research_case(
            case_id=args.case_id,
            symbol=args.symbol.upper(),
            strategy_name=args.strategy_name.upper(),
        )
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Research-case input template: {path}")
        return

    if args.input_json:
        input_path = Path(args.input_json)
        if not input_path.exists():
            raise FileNotFoundError(
                f"Research-case input not found: {input_path}"
            )
        payload = json.loads(
            input_path.read_text(encoding="utf-8")
        )
        mode = f"manifest: {input_path}"
    else:
        payload = demo_research_case(
            case_id=args.case_id,
            symbol=args.symbol.upper(),
            strategy_name=args.strategy_name.upper(),
        )
        mode = "deterministic demo manifest"

    result = ResearchCaseEngine().build(
        case_id=str(payload["case_id"]),
        symbol=str(payload["symbol"]),
        strategy_name=str(payload["strategy_name"]),
        title=str(payload["title"]),
        primary_thesis=str(payload["primary_thesis"]),
        time_horizon=str(payload["time_horizon"]),
        review_date=payload["review_date"],
        confidence_score=float(payload["confidence_score"]),
        scenarios=tuple(payload.get("scenarios", ())),
        evidence=tuple(payload.get("evidence", ())),
        assumptions=tuple(payload.get("assumptions", ())),
        metadata={
            "source": "RESEARCH_CASE_CLI",
        },
    )
    output = write_research_case_report(
        result,
        args.output,
    )

    print("Milestone 34 Phase 4 research case completed.")
    print(f"Input mode: {mode}")
    print(f"Output: {output}")
    print(f"Status: {result.status}")
    print(f"Score: {result.research_score:.2f}")
    print(f"Grade: {result.research_grade}")


if __name__ == "__main__":
    main()
