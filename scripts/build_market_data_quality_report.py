import argparse, json
from pathlib import Path
from trading_ai.market.market_data_quality_reporting import MarketDataQualityReport

def read_json(path):
    if not path: return None
    p=Path(path)
    return json.loads(p.read_text()) if p.exists() else None

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--pipeline-json")
    parser.add_argument("--feed-json")
    parser.add_argument("--reconciliation-json")
    parser.add_argument("--output",default="reports/market_data_quality.html")
    args=parser.parse_args()
    path=MarketDataQualityReport().generate(
        pipeline_profile=read_json(args.pipeline_json),
        feed_profile=read_json(args.feed_json),
        reconciliation_summary=read_json(args.reconciliation_json),
        path=args.output,
    )
    print(f"Market-data quality report: {path}")
if __name__=="__main__": main()
