import csv
from pathlib import Path


def latest_file(pattern):
    files = sorted(Path("reports").glob(pattern), reverse=True)
    return files[0] if files else None


def main():

    latest = latest_file("scanner_results_*.csv")

    if latest is None:
        print("No scanner results found.")
        return

    with open(latest, "r") as f:
        rows = list(csv.DictReader(f))

    print()
    print("========== Option Details ==========")
    print(f"Source: {latest}")
    print()

    for r in rows:
        print(f"{r['symbol']} {r['expiry']} {r['strike']} {r['signal']}")
        print(f"  Strategy        : {r.get('strategy')}")
        print(f"  Confidence      : {r.get('confidence')}")
        print(f"  Rank Score      : {r.get('rank_score')}")
        print(f"  Option Score    : {r.get('option_score')}")
        print(f"  POP             : {r.get('probability_of_profit')}")
        print(f"  Liquidity Score : {r.get('liquidity_score')}")
        print(f"  Delta Score     : {r.get('delta_score')}")
        print(f"  IV Score        : {r.get('iv_score')}")
        print(f"  Win Probability : {r.get('win_probability')}")
        print(f"  Reward/Risk     : {r.get('reward_risk')}")
        print(f"  Kelly           : {r.get('kelly_fraction')}")
        print(f"  Option Price    : {r.get('option_price_estimate')}")
        print(f"  Contract Cost   : {r.get('estimated_contract_cost')}")
        print(f"  Delta           : {r.get('delta')}")
        print(f"  IV              : {r.get('iv')}")
        print(f"  Open Interest   : {r.get('open_interest')}")
        print(f"  DTE             : {r.get('days_to_expiry')}")
        print()

    print("====================================")
    print()


if __name__ == "__main__":
    main()
