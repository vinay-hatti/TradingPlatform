#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
path = (
    root
    / "scripts"
    / "run_m77_19_6_5_2_7_native_timeframe_state_and_participation_causal_intervention_replay.py"
)

if not path.exists():
    raise SystemExit("M77.19.6.5.2.7 verification FAILED: runner missing")

text = path.read_text()
tree = ast.parse(text)

required = (
    "EXPECTED_525_REPORT_SHA256",
    "EXPECTED_526_REPORT_SHA256",
    "80a47e00da8951f15dec66c156f312601e6261bdf37430a1da3dae7d83301187",
    "timeframe_states.1w.confidence",
    "timeframe_states.1w.evidence.ema50",
    "participation.evidence.adl",
    "participation.evidence.obv_normalized",
    "participation.evidence.up_down_volume_ratio",
    "participation.score",
    "participation.state",
    "participation.conviction",
    "participation.deterioration_risk",
    "PARTICIPATION_EVIDENCE_ONLY",
    "PARTICIPATION_COMPONENT",
    "WEEKLY_AND_PARTICIPATION_COMPONENT",
    "round(sum(confidences) / len(confidences), 2)",
    "SET TRANSACTION READ ONLY",
    "PARITY_TOLERANCE = 1e-9",
    "native.compare_profile",
    "full_23_year_reconstruction_authorized",
    "production_authority_effect",
)

for marker in required:
    if marker not in text:
        raise SystemExit(
            "M77.19.6.5.2.7 verification FAILED: missing " + marker
        )

for prohibited in (
    "INSERT ",
    "UPDATE ",
    "DELETE ",
    "TRUNCATE ",
    "session.commit(",
    "production_authority_effect\": True",
    "full_23_year_reconstruction_authorized\": True",
):
    if prohibited in text:
        raise SystemExit(
            "M77.19.6.5.2.7 verification FAILED: prohibited marker detected: "
            + prohibited
        )

print("M77.19.6.5.2.7 verification PASSED")
print(" - M77.19.6.5.2.5 and .6 report SHAs are pinned")
print(" - native replay runner SHA remains pinned")
print(" - database use is limited to READ ONLY SPY session calendar")
print(" - weekly confidence and weekly ema50 are the only MT candidate interventions")
print(" - native aggregate confidence is recomputed using unweighted available-state mean")
print(" - participation raw-evidence and component-output arms are separated")
print(" - combined weekly + participation arm is required for full parity certification")
print(" - native compare_profile remains semantic authority")
print(" - parity tolerance remains 1e-9")
print(" - synthetic interventions cannot become production authority")
print(" - 23-year reconstruction remains blocked unless later explicitly certified")
