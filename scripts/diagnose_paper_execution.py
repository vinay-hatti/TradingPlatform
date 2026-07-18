from trading_ai.ui.services.paper_execution_service import PaperExecutionService


def main():
    state = PaperExecutionService().state()
    print("=== Broker-Backed Paper Execution ===")
    print(f"Broker Adapter        : {state.summary.broker_adapter}")
    print(f"Live Trading Enabled  : {state.summary.live_trading_enabled}")
    print(f"Total Orders          : {state.summary.total_orders}")
    print(f"Open Orders           : {state.summary.open_orders}")
    print(f"Total Fills           : {state.summary.total_fills}")
    print(f"Total Positions       : {state.summary.total_positions}")
    print(f"Gross Market Value    : ${state.summary.gross_market_value:,.2f}")
    print(f"Unrealized P&L        : ${state.summary.total_unrealized_pnl:,.2f}")
    print(f"Reconciliation        : {state.summary.reconciliation_status}")
    print(f"Reconciliation Issues : {state.reconciliation.issue_count}")


if __name__ == "__main__":
    main()
