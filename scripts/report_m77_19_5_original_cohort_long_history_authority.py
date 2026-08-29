#!/usr/bin/env python3
import json
from pathlib import Path
x=json.loads(Path("reports/m77/m77_19_5_original_cohort_long_history_certification.json").read_text())
print("=== M77.19.5 ORIGINAL-COHORT LONG-HISTORY SOURCE AUTHORITY ===")
print("certified_for_m77_19_6_reconstruction:",x["certified_for_m77_19_6_reconstruction"]);print("authority_semantics:",x["authority_semantics"]);print("survivorship_bias_explicit:",x["survivorship_bias_explicit"]);print("summary:",x["summary"])
for k,v in x["gates"].items():print(k,v)
print("next_step:",x["next_step"]);print("production_authority_effect:",x["production_authority_effect"])
