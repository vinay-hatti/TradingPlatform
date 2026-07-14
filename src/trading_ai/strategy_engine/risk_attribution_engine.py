from trading_ai.strategy_engine.risk_surface_profile import RiskAttribution


class RiskAttributionEngine:
    def attribute(self, point):
        components = {
            "DELTA": float(point.delta_component),
            "GAMMA": float(point.gamma_component),
            "VEGA": float(point.vega_component),
            "THETA": float(point.theta_component),
            "RHO": float(point.rho_component),
        }
        denominator = sum(abs(value) for value in components.values())
        return [
            RiskAttribution(
                factor=name,
                pnl=value,
                contribution_pct=(abs(value) / denominator if denominator else 0.0),
                adverse=value < 0.0,
            )
            for name, value in components.items()
        ]
