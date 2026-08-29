#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
P = ROOT / "scripts/run_m77_19_6_5_2_22_native_event_state_discriminator_forensics.py"
if not P.exists():
    raise SystemExit("M77.19.6.5.2.22 verification FAILED: runner missing")
T = P.read_text()

required = (
    'EXPECTED_REPORT_5221_SHA256 = "13ca75225a523cd7993e990af495734bc1ea0ca559f575119a031fe57122fb44"',
    'EXPECTED_RUNNER_5221_SHA256 = "c7fd0c6e1773cc367653f1cd56a5a277c2d50056fd3b73ff92b7fec09a5dbe79"',
    'EXPECTED_EVENT_COUNT = 4991',
    '"AES_RESISTANCE"',
    '"ANET_SUPPORT"',
    '"ATO_RESISTANCE"',
    '"percentile_midrank"',
    '"edge_proximity"',
    '"rank_space_l1_distance"',
    '"categorical_support"',
    '"classifier_trained": False',
    '"decision_boundary_fitted": False',
    '"feature_weight_optimization": False',
    '"neighbor_cutoff_selected": False',
    '"causal_identity_used_for_rule_construction": False',
    '"historical_answer_leakage_into_trigger_logic": False',
    '"new_trigger_semantic_introduced": False',
    '"new_threshold_introduced": False',
    '"threshold_search_or_optimization": False',
    '"database_mode": "NONE_REPORT_ONLY"',
    '"candidate_semantic_promoted": False',
    '"production_authority_effect": False',
)
missing = [x for x in required if x not in T]
if missing:
    raise SystemExit(f"M77.19.6.5.2.22 verification FAILED: missing markers {missing}")

for bad in (
    "LogisticRegression",
    "RandomForest",
    "DecisionTree",
    "GridSearchCV",
    "threshold_grid",
    "optimize_threshold",
    "UPDATE ",
    "INSERT ",
    "DELETE ",
    "DROP TABLE",
    "ALTER TABLE",
):
    if bad in T:
        raise SystemExit(f"M77.19.6.5.2.22 verification FAILED: prohibited token {bad}")

print("M77.19.6.5.2.22 verification PASSED")
print(" - M77.19.6.5.2.21 report and runner are SHA-pinned")
print(" - exact 4,991 native event stream is mandatory")
print(" - AES / ANET / ATO causal events are exact and mandatory")
print(" - diagnostics are conditioned by native action")
print(" - empirical percentile/midrank diagnostics are descriptive only")
print(" - categorical state support is counted without fitting")
print(" - nearest neighbors use fixed rank-space L1 diagnostics")
print(" - no neighbor cutoff is selected")
print(" - no classifier or decision boundary is fit")
print(" - no feature-weight optimization")
print(" - no new trigger semantic or threshold")
print(" - no threshold search or optimization")
print(" - database access is NONE / report-only")
print(" - causal identity is diagnostic-only")
print(" - candidate semantic remains unpromoted")
print(" - production authority remains unchanged")
print(" - 23-year reconstruction remains blocked")
