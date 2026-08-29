from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path

from trading_ai.database import SessionLocal
from trading_ai.historical_underlying_replay.service import (
    HistoricalUnderlyingReplayService,
)

VERSION = "M77.2-MULTIYEAR-FROZEN-CHAMPION-1.0"
DEFAULT_START = date(2022, 10, 14)
DEFAULT_END = date(2026, 8, 17)


def _segments(start: date, end: date):
    year = start.year
    while year <= end.year:
        seg_start = max(start, date(year, 1, 1))
        seg_end = min(end, date(year, 12, 31))
        yield year, seg_start, seg_end
        year += 1


def _load_manifest(path: Path):
    if not path.exists():
        return {
            "version": VERSION,
            "governance": {
                "production_authority_effect": False,
                "production_model_mutation": False,
                "automatic_champion_promotion": False,
            },
            "segments": [],
        }
    return json.loads(path.read_text())


def _save_manifest(path: Path, manifest):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(manifest, default=str, indent=2) + "\n")
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="M77.2 resumable multi-year frozen-champion historical replay"
    )
    parser.add_argument("--start", default=DEFAULT_START.isoformat())
    parser.add_argument("--end", default=DEFAULT_END.isoformat())
    parser.add_argument(
        "--cadence", choices=["WEEKLY", "MONTHLY"], default="WEEKLY"
    )
    parser.add_argument("--symbols")
    parser.add_argument(
        "--manifest",
        default="reports/m77/m77_2_multiyear_frozen_champion_manifest.json",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore any existing manifest and start a new set of replay segments.",
    )
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if end < start:
        raise SystemExit("--end must be >= --start")
    if start < DEFAULT_START:
        raise SystemExit(
            "M77.2 certification start may not precede 2022-10-14 because "
            "the governed 300-session warm-up is not available earlier."
        )

    manifest_path = Path(args.manifest)
    if args.fresh and manifest_path.exists():
        manifest_path.unlink()
    manifest = _load_manifest(manifest_path)
    complete_keys = {
        (int(item["year"]), str(item["start"]), str(item["end"]))
        for item in manifest.get("segments", [])
        if item.get("status") in {"READY", "DEGRADED"}
        and item.get("replay_run_id")
    }

    symbols = (
        [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        if args.symbols
        else None
    )

    with SessionLocal() as session:
        service = HistoricalUnderlyingReplayService(session)

        for year, seg_start, seg_end in _segments(start, end):
            key = (year, seg_start.isoformat(), seg_end.isoformat())
            if key in complete_keys:
                print(
                    f"[M77.2] {year} already complete in manifest; skipping "
                    f"{seg_start} -> {seg_end}"
                )
                continue

            print(
                f"[M77.2] running frozen champion: "
                f"{seg_start} -> {seg_end} cadence={args.cadence}"
            )
            result = service.run_champion_baseline(
                start=seg_start,
                end=seg_end,
                cadence=args.cadence,
                symbols=symbols,
            )
            segment = {
                "year": year,
                "start": seg_start.isoformat(),
                "end": seg_end.isoformat(),
                "cadence": args.cadence,
                **result,
            }
            manifest.setdefault("segments", []).append(segment)
            manifest["status"] = (
                "DEGRADED"
                if any(s.get("status") != "READY" for s in manifest["segments"])
                else "READY"
            )
            manifest["replay_run_ids"] = [
                s["replay_run_id"]
                for s in manifest["segments"]
                if s.get("replay_run_id")
            ]
            _save_manifest(manifest_path, manifest)
            print(json.dumps(segment, default=str, indent=2))

    print("\n=== M77.2 MULTI-YEAR REPLAY MANIFEST ===")
    print(json.dumps(manifest, default=str, indent=2))
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
