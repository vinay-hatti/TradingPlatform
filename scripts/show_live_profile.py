import json
from pathlib import Path


def main():

    path = Path("reports/walkforward/live_profile.json")

    if not path.exists():
        raise FileNotFoundError(
            "live_profile.json not found. Run select-live-profile first."
        )

    with open(path, "r") as f:
        profile = json.load(f)

    print()
    print("========== Current Live Profile ==========")
    print(f"Profile      : {profile['profile']}")
    print(f"Score        : {profile['score']:.2f}")
    print(f"Total PnL    : ${profile['total_pnl']:,.2f}")
    print(f"Avg Return   : {profile['avg_return']:.2%}")
    print(f"Avg PF       : {profile['avg_pf']:.2f}")
    print(f"Consistency  : {profile['consistency']:.2%}")
    print(f"Trades       : {profile['total_trades']}")
    print("==========================================")
    print()


if __name__ == "__main__":
    main()
