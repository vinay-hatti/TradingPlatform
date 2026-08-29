#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

DEFAULT = Path("reports/m77/m77_8_daily_pit_replay_authority.json")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT))
    ap.add_argument("--show-regimes", action="store_true")
    args=ap.parse_args()
    p=Path(args.input)
    if not p.exists():
        raise SystemExit(f"M77.8 artifact not found: {p}")
    d=json.loads(p.read_text())
    print("=== M77.8 DAILY PIT REPLAY AUTHORITY ===")
    print(f"Version: {d.get('version')}")
    print(f"Status: {d.get('status')}")
    print(f"Production authority effect: {d.get('production_authority_effect')}")
    print("\n--- DAILY CONTRACT ---")
    for k,v in (d.get('daily_contract') or {}).items(): print(f"{k}: {v}")
    print("\n--- PRICE ADJUSTMENT PROVENANCE ---")
    for k,v in (d.get('price_adjustment_provenance') or {}).items(): print(f"{k}: {v}")
    print("\n--- FROZEN WEEKLY PARITY ---")
    for k,v in (d.get('frozen_weekly_parity') or {}).items():
        if k != 'mismatches': print(f"{k}: {v}")
    print("\n--- ACCEPTANCE ---")
    for k,v in (d.get('acceptance') or {}).items(): print(f"{k}: {v}")
    if args.show_regimes:
        print("\n--- DAILY REGIME COUNTS ---")
        for k,v in sorted((d.get('regime_authority') or {}).get('regime_counts',{}).items()): print(f"{k}: {v}")
    print(f"\nNext step: {d.get('next_step')}")

if __name__=='__main__': main()
