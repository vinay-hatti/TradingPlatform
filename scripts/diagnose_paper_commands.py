from trading_ai.ui.services.paper_command_service import PaperCommandService


def main():
    state = PaperCommandService().state()
    print("=== Governed Paper Trading ===")
    print(f"Environment       : {state.summary.environment}")
    print(f"Mode              : {state.summary.mode}")
    print(f"Live Enabled      : {state.summary.live_trading_enabled}")
    print(f"Total Orders      : {state.summary.total_orders}")
    print(f"Open Orders       : {state.summary.open_orders}")
    print(f"Filled Orders     : {state.summary.filled_orders}")
    print(f"Cancelled Orders  : {state.summary.cancelled_orders}")
    print(f"Rejected Orders   : {state.summary.rejected_orders}")
    print(f"Gross Notional    : ${state.summary.gross_notional:,.2f}")
    print("Safety Notices:")
    for notice in state.safety_notices:
        print(f"- {notice}")


if __name__ == "__main__":
    main()
