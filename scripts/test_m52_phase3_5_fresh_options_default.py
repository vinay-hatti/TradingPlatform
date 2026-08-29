from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.run_market_ingestion import (
    _default_reuse_age_minutes,
    _resolve_force_controls,
    _validate_option_controls,
    build_parser,
)
from trading_ai.scanner.options_market_data_ingestion import IngestionManifestStore


def main() -> None:
    parser = build_parser()
    normal = _validate_option_controls(_resolve_force_controls(parser.parse_args(["--data-scope", "all"])))
    assert normal.data_scope == "all"
    assert normal.reuse_options_snapshot is False
    assert normal.force_options_refresh is False

    reuse = _validate_option_controls(_resolve_force_controls(parser.parse_args(["--reuse-options-snapshot"])))
    assert reuse.reuse_options_snapshot is True

    forced = _validate_option_controls(_resolve_force_controls(parser.parse_args(["--force-refresh"])))
    assert forced.force_options_refresh
    assert forced.force_dealer_refresh
    assert forced.force_underlying_refresh
    assert forced.force_market_overview_refresh

    try:
        _validate_option_controls(
            _resolve_force_controls(parser.parse_args(["--reuse-options-snapshot", "--force-options-refresh"]))
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Conflicting reuse/force options must fail")

    assert _default_reuse_age_minutes(datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc)) == 60
    assert _default_reuse_age_minutes(datetime(2026, 7, 27, 23, 0, tzinfo=timezone.utc)) == 4320

    with TemporaryDirectory() as directory:
        store = IngestionManifestStore(Path(directory) / "manifest.json")
        store.begin_cycle("cycle-1", metadata={"mode": "FRESH"})
        store.mark_completed("stable-batch", cycle_id="cycle-1")
        assert store.is_completed("stable-batch", cycle_id="cycle-1")
        assert not store.is_completed("stable-batch", cycle_id="cycle-2")
        store.complete_cycle("cycle-1", metadata={"valid_records": 10})
        latest = store.latest_cycle()
        assert latest and latest["cycle_id"] == "cycle-1"
        assert latest["metadata"]["valid_records"] == 10

    print("Milestone 52 Phase 3.5 fresh-options-default assertions passed.")


if __name__ == "__main__":
    main()
