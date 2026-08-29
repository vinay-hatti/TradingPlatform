#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    contracts = (root / "src/trading_ai/outcome_probability/contracts.py").read_text()
    features = (root / "src/trading_ai/outcome_probability/features.py").read_text()
    labels = (root / "src/trading_ai/outcome_probability/labels.py").read_text()
    engine = (root / "src/trading_ai/outcome_probability/engine.py").read_text()
    service = (root / "src/trading_ai/outcome_probability/service.py").read_text()
    orchestration = (root / "src/trading_ai/stock_intelligence/orchestration.py").read_text()
    profile = (root / "src/trading_ai/stock_intelligence/profile.py").read_text()
    decision = (root / "src/trading_ai/stock_intelligence/decision_intelligence.py").read_text()
    ingestion = (root / "src/trading_ai/institutional_options/opportunity_ingestion.py").read_text()
    ui = (root / "ui/workstation/src/StockIntelligenceScannerPage.tsx").read_text()
    migration = (root / "migrations/versions/m77_001_governed_outcome_probability.py").read_text()
    operator = (root / "scripts/run_m77_outcome_probability.py").read_text()
    operator_policy = (root / "src/trading_ai/outcome_probability/operator.py").read_text()
    checks = {
        "barrier_targets": all(token in contracts for token in ("target_1_before_stop", "target_2_before_stop", "profitable_at_horizon", "thesis_invalidation")),
        "point_in_time_allow_list": "future_fields_excluded" in features and "FORBIDDEN_FEATURE_TOKENS" in features,
        "ambiguous_same_bar_excluded": "TARGET_{index}_AND_STOP_SAME_DAILY_BAR" in labels and "same_bar_order_assumed" in service,
        "chronological_partitions": all(token in engine for token in ("train_end", "calibration_end", "same_as_of_date_cross_partition")),
        "forward_horizon_purge": all(token in engine for token in ("horizon_dates", "label_horizon_overlap_cross_partition", "purged_for_forward_horizon")),
        "proper_scoring": all(token in engine for token in ("brier_score_loss", "log_loss", "roc_auc_score", "calibrated_ece")),
        "uncertainty_and_abstention": all(token in engine for token in ("epistemic_uncertainty", "out_of_distribution_score", 'return "ABSTAIN"')),
        "human_governed_shadow": all(token in service for token in ("APPROVED_SHADOW", "SHADOW_ACTIVE", '"authority_effect": False')),
        "canonical_authority_hash_isolation": "decision.pop('outcome_probability',None)" in profile and '"outcome_probability": self.outcome_probability' not in decision,
        "scanner_integration": "attach_shadow_assessment" in orchestration and "record_prediction" in orchestration,
        "institutional_options_integration": "M77 shadow probability" in ingestion,
        "ui_explainability": "M77 outcome probability" in ui,
        "schema": all(token in migration for token in ("outcome_probability_observations", "outcome_probability_model_artifacts", "outcome_probability_predictions", "outcome_probability_audit_events")),
        "readiness_exit_contract": (
            all(
                token in operator_policy
                for token in ('command == "train"', 'status") == "INSUFFICIENT_EVIDENCE"')
            )
            and "from trading_ai.outcome_probability.operator import result_exit_code"
            in operator
            and "result_exit_code(args.command, result)" in operator
        ),
    }
    result = {
        "version": "M77.0-STATIC-RELEASE-VERIFICATION-1.0",
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
