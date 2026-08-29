from __future__ import annotations

import importlib.util
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "run_market_ingestion.py"
spec = importlib.util.spec_from_file_location("run_market_ingestion_m52_phase36", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def parsed(*argv: str):
    return module._validate_option_controls(
        module._resolve_force_controls(
            module._apply_mode_preset(module.build_parser().parse_args(list(argv)))
        )
    )


daily = parsed()
assert daily.mode == "daily"
assert daily.data_scope == "all"
assert daily.reuse_options_snapshot is False
assert daily.force_options_refresh is False

intraday = parsed("--mode", "intraday")
assert intraday.data_scope == "options"
assert intraday.reuse_options_snapshot is False

analytics = parsed("--mode", "analytics")
assert analytics.data_scope == "all"
assert analytics.reuse_options_snapshot is True

recovery = parsed("--mode", "recovery")
assert recovery.data_scope == "all"
assert recovery.force_underlying_refresh
assert recovery.force_options_refresh
assert recovery.force_dealer_refresh
assert recovery.force_market_overview_refresh

legacy = parsed("--data-scope", "options")
assert legacy.data_scope == "options"
assert legacy.mode == "daily"

try:
    parsed("--mode", "analytics", "--force-options-refresh")
except ValueError:
    pass
else:
    raise AssertionError("analytics and force-options must be rejected")

with tempfile.TemporaryDirectory() as td:
    report = Path(td) / "lifecycle.json"
    args = parsed("--mode", "intraday", "--lifecycle-report", str(report), "--skip-publication")
    started = datetime.now(timezone.utc) - timedelta(seconds=2)
    completed = datetime.now(timezone.utc)
    module._write_lifecycle_report(
        args,
        started_at=started,
        completed_at=completed,
        failed=0,
        post_ingestion_failed=False,
        underlying_refreshed=False,
        options_refreshed=True,
        dealer_refreshed=True,
        publication=None,
    )
    payload = json.loads(report.read_text())
    assert payload["mode"] == "intraday"
    assert payload["stages"]["options"]["mode"] == "FRESH"
    assert payload["stages"]["options"]["refreshed"] is True
    assert payload["status"] == "READY"

print("Milestone 52 Phase 3.6 ingestion lifecycle assertions passed.")
