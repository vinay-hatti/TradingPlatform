from trading_ai.risk.position_sizer import PositionSizer


def main():

    sizer = PositionSizer(
        risk_per_trade_pct=0.01,
        max_position_pct=0.10,
    )

    print()
    print("========== Position Sizer Test ==========")

    for price in [2.5, 5, 10, 20, 50]:

        contracts = sizer.contracts(
            capital=100000,
            option_price=price,
        )

        cost = contracts * price * 100.0

        print(
            f"${price:>5} option -> "
            f"{contracts:>3} contracts | "
            f"Cost=${cost:,.2f}"
        )

    print("=========================================")
    print()


if __name__ == "__main__":
    main()
