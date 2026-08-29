from trading_ai.options.pricing import BlackScholesPricingEngine


def main():

    engine = BlackScholesPricingEngine(
        risk_free_rate=0.04,
    )

    spot = 300.0
    strike = 300.0
    volatility = 0.28
    dte = 30

    print()
    print("========== Black-Scholes Pricing Test ==========")

    for option_type in ["CALL", "PUT"]:
        price = engine.price(
            option_type,
            spot,
            strike,
            volatility,
            dte,
        )

        delta = engine.delta(
            option_type,
            spot,
            strike,
            volatility,
            dte,
        )

        theta = engine.theta(
            option_type,
            spot,
            strike,
            volatility,
            dte,
        )

        print(
            f"{option_type:4} | "
            f"Price=${price:8.2f} | "
            f"Delta={delta:7.4f} | "
            f"Gamma={engine.gamma(spot, strike, volatility, dte):8.5f} | "
            f"Theta={theta:8.4f} | "
            f"Vega={engine.vega(spot, strike, volatility, dte):7.4f} | "
            f"Rho={engine.rho(option_type, spot, strike, volatility, dte):7.4f}"
        )

    print("================================================")
    print()


if __name__ == "__main__":
    main()
