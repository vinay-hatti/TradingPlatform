from trading_ai.options.pricing_service import OptionPricingService


def main():

    service = OptionPricingService(
        risk_free_rate=0.04,
        default_dte=30,
    )

    spot = 300.0
    hv20 = 0.28

    print()
    print("========== Option Pricing Service Test ==========")

    for signal in ["CALL", "PUT"]:

        price = service.option_price(
            signal=signal,
            spot=spot,
            strike=spot,
            hv20=hv20,
            dte=30,
        )

        greeks = service.greeks(
            signal=signal,
            spot=spot,
            strike=spot,
            hv20=hv20,
            dte=30,
        )

        print(
            f"{signal:4} | "
            f"Price=${price:8.2f} | "
            f"Delta={greeks['delta']:7.4f} | "
            f"Gamma={greeks['gamma']:8.5f} | "
            f"Theta={greeks['theta']:8.4f} | "
            f"Vega={greeks['vega']:7.4f} | "
            f"Vol={greeks['volatility']:6.2%} | "
            f"DTE={greeks['dte']}"
        )

    print("=================================================")
    print()


if __name__ == "__main__":
    main()
