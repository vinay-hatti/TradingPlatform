import csv
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from trading_ai.scanner.universe_management import LiquidityGovernanceService


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp); universe = root / "universe.csv"; metrics = root / "metrics.csv"
        with universe.open("w", newline="") as h:
            w=csv.DictWriter(h, fieldnames=["symbol","name","exchange","asset_type","options_eligible"]); w.writeheader();
            w.writerows([{"symbol":"A","name":"A","exchange":"NASDAQ","asset_type":"EQUITY","options_eligible":"true"},{"symbol":"B","name":"B","exchange":"NYSE","asset_type":"EQUITY","options_eligible":"false"}])
        with metrics.open("w", newline="") as h:
            fields=["symbol","as_of","price","average_daily_volume","average_daily_dollar_volume","bid_ask_spread_pct","market_cap","option_volume","option_open_interest","halted"]
            w=csv.DictWriter(h, fieldnames=fields); w.writeheader(); now=datetime.now(timezone.utc).isoformat()
            w.writerow({"symbol":"A","as_of":now,"price":100,"average_daily_volume":1000000,"average_daily_dollar_volume":100000000,"bid_ask_spread_pct":0.01,"market_cap":10000000000,"option_volume":100,"option_open_interest":1000,"halted":"false"})
        result=LiquidityGovernanceService().screen(universe_csv=universe, metrics_csv=metrics, output_dir=root/"out", report_dir=root/"reports")
        assert result.evaluated_count==2 and result.eligible_count==1 and result.missing_metrics_count==1
        assert all(Path(path).is_file() for path in result.artifacts.values())
        print("M35 Phase 1 Step 4 service and reporting assertions passed.")
if __name__ == "__main__": main()
