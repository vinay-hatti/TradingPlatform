from trading_ai.ui.services.portfolio_risk_service import PortfolioRiskService


def main():
    result = PortfolioRiskService().get()
    print(f"Available: {result.available}")
    print(f"Stale: {result.stale}")
    print(f"Source: {result.source_detail}")
    print(f"Open positions: {result.summary.open_positions}")
    print(f"Capital: {result.summary.capital}")
    print(f"Total P&L: {result.summary.total_pnl}")
    print(f"Risk level: {result.risk.risk_level}")
    print("Limits:")
    for item in result.limits:
        print(
            f"  - {item.name}: {item.status} "
            f"current={item.current_value} "
            f"limit={item.limit_value}"
        )
    print("Notices:")
    for notice in result.notices:
        print(f"  - {notice}")


if __name__ == "__main__":
    main()
