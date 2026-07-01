from trading_ai.risk.portfolio_risk import PortfolioRiskManager


def main():

    risk = PortfolioRiskManager(
        capital=100000.0,
        max_portfolio_heat=0.25,
        max_symbol_exposure=0.10,
        max_sector_exposure=0.30,
        max_strategy_exposure=0.70,
        min_cash_reserve=0.20,
        max_net_delta=2.0,
    )

    current_positions = []

    candidate = {
        "symbol": "AAPL",
        "signal": "CALL",
        "strategy": "LONG_CALL",
        "option_price_estimate": 44.59,
        "recommended_contracts": 1,
        "delta": 0.45,
    }

    result = risk.evaluate(
        current_positions=current_positions,
        candidate_trade=candidate,
        sector="Technology",
        cash=100000.0,
    )

    print(result)


if __name__ == "__main__":
    main()
