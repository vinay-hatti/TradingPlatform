import argparse
from trading_ai.ui.services.symbol_intelligence_service import SymbolIntelligenceService

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol", nargs="?", default="SPY")
    parser.add_argument("--days", type=int, default=252)
    args = parser.parse_args()
    result = SymbolIntelligenceService().get(args.symbol, args.days)
    print(f"Symbol: {result.symbol}")
    print(f"Price source: {result.price_source}")
    print(f"Price points: {len(result.price_history)}")
    print(f"Opportunities: {len(result.opportunity_history)}")
    for notice in result.notices:
        print(f"- {notice}")

if __name__ == "__main__":
    main()
