from trading_ai.execution.paper_broker import PaperBroker


def money(value):
    return f"${float(value):,.2f}"


def main():

    broker = PaperBroker(initial_cash=100000.0)
    summary = broker.summary()

    print()
    print("========== Paper Trading Status ==========")
    print(f"Cash           : {money(summary['cash'])}")
    print(f"Open Value     : {money(summary['open_value'])}")
    print(f"Net Liquidation: {money(summary['net_liquidation'])}")
    print(f"Unrealized PnL : {money(summary['unrealized_pnl'])}")
    print(f"Realized PnL   : {money(summary['realized_pnl'])}")
    print()

    print("Open Positions:")
    open_positions = broker.open_positions()

    if not open_positions:
        print("  None")
    else:
        for p in open_positions:
            print(
                f"  {p['symbol']:5} | "
                f"{p['signal']:4} | "
                f"{p['strategy']:10} | "
                f"Qty={int(p['quantity']):3} | "
                f"Strike={float(p['strike']):8.2f} | "
                f"Exp={p['expiry']} | "
                f"Entry={money(p['entry_price'])} | "
                f"Current={money(p['current_price'])} | "
                f"Unrealized={money(p.get('unrealized_pnl', 0.0))}"
            )

    print()
    print("Closed Positions:")
    closed_positions = broker.closed_positions()

    if not closed_positions:
        print("  None")
    else:
        for p in closed_positions:
            print(
                f"  {p['symbol']:5} | "
                f"{p['signal']:4} | "
                f"{p['strategy']:10} | "
                f"Qty={int(p['quantity']):3} | "
                f"Entry={money(p['entry_price'])} | "
                f"Exit={money(p.get('exit_price', 0.0))} | "
                f"Reason={p.get('exit_reason')} | "
                f"Realized={money(p.get('realized_pnl', 0.0))}"
            )

    print("==========================================")
    print()


if __name__ == "__main__":
    main()
