import argparse
from datetime import date
from pathlib import Path
from trading_ai.scanner.cross_asset_data_foundation.reporting import render_console_report
from trading_ai.scanner.cross_asset_data_foundation.serialization import write_json_atomic
from trading_ai.scanner.cross_asset_data_foundation.service import CrossAssetFeatureService

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--as-of-date", required=True)
    p.add_argument("--output-dir", default="reports/m35/phase5/cross_asset_data_foundation")
    a = p.parse_args()
    out = Path(a.output_dir); out.mkdir(parents=True, exist_ok=True)
    profile = CrossAssetFeatureService().run(
        as_of_date=date.fromisoformat(a.as_of_date),
        output_path=out / "cross_asset_features.jsonl",
    )
    run_path = write_json_atomic(out / "run.json", profile)
    print(render_console_report(profile))
    print(f"Run report          : {run_path}")

if __name__ == "__main__":
    main()
