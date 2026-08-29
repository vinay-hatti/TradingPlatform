#!/usr/bin/env python3
import json
from pathlib import Path
x=json.loads(Path("reports/m77/m77_19_multi_cadence_long_history_replication_authority_audit.json").read_text())
print("=== M77.19 MULTI-CADENCE LONG-HISTORY AUTHORITY AUDIT ===")
print("exact_5773_session_replication_authorized:",x["exact_5773_session_replication_authorized"])
print("disposition:",x["disposition"])
print("cadence_state_coverage:",x["cadence_state_coverage"])
print("pit_regime_coverage:",x["pit_regime_coverage"])
print("gates:",x["gates"])
print("authority_gaps:",x["authority_gaps"])
print("original_M77_11:",x["original_M77_11"])
print("original_M77_12:",x["original_M77_12"])
print("next_step:",x["next_step"])
