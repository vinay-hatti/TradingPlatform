#!/usr/bin/env python3
import json
from pathlib import Path

p = Path("reports/m77/m77_19_4_adapter_source_semantics_capture.json")
if not p.exists():
    raise SystemExit("Run M77.19.4 capture first")
x = json.loads(p.read_text())

print("=== M77.19.4 ADAPTER SOURCE SEMANTICS CAPTURE ===")
print("status:", x["status"])
print("source_file_count:", x["source_file_count"])
print("bundle_path:", x.get("bundle_path"))
print("bundle_sha256:", x.get("bundle_sha256"))
print("production_authority_effect:", x["production_authority_effect"])

print("\n--- PRIMARY SOURCES ---")
for k, v in x["primary_sources"].items():
    print(k, v)

print("\n--- CAPTURED FILES ---")
for f in x["files"]:
    print(f["path"], "sha256=", f["sha256"], "bytes=", f["size_bytes"])
    pa = f.get("python_analysis")
    if pa:
        print("  parse_ok:", pa.get("parse_ok"))
        print("  argparse:", pa.get("argparse_options"))
        print("  functions:", [z["name"] for z in pa.get("top_level_functions", [])])
        print("  imports:", pa.get("imports"))

print("next_step:", x["next_step"])
