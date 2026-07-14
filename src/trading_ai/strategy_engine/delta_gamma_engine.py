class DeltaGammaEngine:
    """Second-order Taylor approximation for option-position P/L."""

    def approximate(
        self,
        underlying_price,
        price_shock_pct,
        volatility_shock,
        time_offset_days,
        net_delta,
        net_gamma,
        net_vega,
        net_theta,
        net_rho=0.0,
        rate_shock=0.0,
        contract_multiplier=100.0,
    ):
        price_change = float(underlying_price) * float(price_shock_pct)
        delta_component = float(net_delta) * price_change * contract_multiplier
        gamma_component = (
            0.5 * float(net_gamma) * price_change * price_change * contract_multiplier
        )
        vega_component = float(net_vega) * float(volatility_shock) * 100.0
        theta_component = float(net_theta) * float(time_offset_days)
        rho_component = float(net_rho) * float(rate_shock) * 100.0
        total = (
            delta_component
            + gamma_component
            + vega_component
            + theta_component
            + rho_component
        )
        return {
            "approximated_pnl": float(total),
            "delta_component": float(delta_component),
            "gamma_component": float(gamma_component),
            "vega_component": float(vega_component),
            "theta_component": float(theta_component),
            "rho_component": float(rho_component),
        }
