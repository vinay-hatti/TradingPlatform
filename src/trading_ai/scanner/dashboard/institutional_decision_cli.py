from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .institutional_decision_profile import (
    InstitutionalDecisionPolicy,
)
from .institutional_decision_serialization import (
    write_institutional_decision_atomic,
)
from .institutional_decision_service import (
    InstitutionalDecisionHandoffService,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Milestone 35 Phase 5 Step 8 institutional decision handoff"
        )
    )
    parser.add_argument(
        "--strategy-comparison-json",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--min-institutional-score",
        type=float,
        default=50.0,
    )
    parser.add_argument(
        "--min-liquidity-score",
        type=float,
        default=40.0,
    )
    parser.add_argument(
        "--min-probability-proxy",
        type=float,
        default=0.20,
    )
    parser.add_argument(
        "--min-reward-risk-ratio",
        type=float,
        default=1.0,
    )
    parser.add_argument(
        "--allow-historical-quotes",
        action="store_true",
    )
    parser.add_argument(
        "--allow-unpriced-strategies",
        action="store_true",
    )
    parser.add_argument(
        "--no-require-defined-risk",
        action="store_true",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "reports/m35/phase5/dashboard/institutional_decision"
        ),
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.strategy_comparison_json.exists():
        raise FileNotFoundError(
            "Strategy-comparison artifact not found: "
            f"{args.strategy_comparison_json}"
        )

    payload = json.loads(
        args.strategy_comparison_json.read_text(
            encoding="utf-8"
        )
    )
    policy = InstitutionalDecisionPolicy(
        min_institutional_score=(
            args.min_institutional_score
        ),
        min_liquidity_score=args.min_liquidity_score,
        min_probability_proxy=args.min_probability_proxy,
        min_reward_risk_ratio=args.min_reward_risk_ratio,
        allow_historical_quotes=args.allow_historical_quotes,
        allow_unpriced_strategies=(
            args.allow_unpriced_strategies
        ),
        require_defined_risk=(
            not args.no_require_defined_risk
        ),
    )

    record = InstitutionalDecisionHandoffService().evaluate(
        payload,
        policy=policy,
    )

    output_path = (
        args.output_dir
        / (
            f"{record.symbol.lower()}_"
            f"{record.direction.lower()}_institutional_decision.json"
        )
    )
    write_institutional_decision_atomic(
        output_path,
        record,
    )

    print(
        json.dumps(
            {
                "symbol": record.symbol,
                "direction": record.direction,
                "decision": record.decision,
                "selected_strategy_id": (
                    record.selected_strategy_id
                ),
                "approved_candidates": (
                    record.approved_candidates
                ),
                "rejected_candidates": (
                    record.rejected_candidates
                ),
                "rejection_summary": (
                    record.rejection_summary
                ),
                "paper_trade_ready": (
                    record.paper_trade_ready
                ),
                "warnings": list(record.warnings),
                "output_json": str(output_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
