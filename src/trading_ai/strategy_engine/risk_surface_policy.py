from dataclasses import dataclass


@dataclass(frozen=True)
class RiskSurfacePolicy:
    """Institutional policy for position and portfolio risk surfaces."""
    price_shocks_pct: tuple[float, ...] = (-0.20,-0.15,-0.10,-0.05,0.0,0.05,0.10,0.15,0.20)
    volatility_shocks: tuple[float, ...] = (-0.20,-0.10,-0.05,0.0,0.05,0.10,0.20)
    time_offsets_days: tuple[int, ...] = (0,1,3,5,10,15,20,30)
    maximum_loss_pct_of_capital: float = 0.08
    severe_loss_pct_of_capital: float = 0.12
    critical_loss_pct_of_capital: float = 0.20
    maximum_gamma_loss_pct_of_capital: float = 0.05
    maximum_vega_loss_pct_of_capital: float = 0.05
    maximum_theta_loss_pct_of_capital: float = 0.03
    minimum_surface_score: float = 55.0
    reject_critical_surface_risk: bool = True
    reject_below_minimum_score: bool = False
    include_rho: bool = True
    maximum_portfolio_loss_pct_of_capital: float = 0.12
    severe_portfolio_loss_pct_of_capital: float = 0.18
    critical_portfolio_loss_pct_of_capital: float = 0.25
    maximum_portfolio_exposure_pct: float = 0.50
    maximum_loss_contribution_pct: float = 0.50
    maximum_capital_weight_pct: float = 0.40
    maximum_loss_concentration_score: float = 0.40
    minimum_diversification_benefit: float = 0.0
    reject_critical_portfolio_risk: bool = True
    reject_portfolio_concentration: bool = False

    def validate(self) -> None:
        if not self.price_shocks_pct or not self.volatility_shocks or not self.time_offsets_days:
            raise ValueError("risk-surface grids must not be empty")
        if 0.0 not in self.price_shocks_pct or 0.0 not in self.volatility_shocks or 0 not in self.time_offsets_days:
            raise ValueError("risk-surface grids must contain their base points")
        if any(day < 0 for day in self.time_offsets_days):
            raise ValueError("time offsets must be non-negative")
        for name in ("minimum_surface_score",):
            value=getattr(self,name)
            if not 0.0 <= value <= 100.0: raise ValueError(f"{name} must be between 0 and 100")
        for name in ("maximum_portfolio_loss_pct_of_capital","severe_portfolio_loss_pct_of_capital","critical_portfolio_loss_pct_of_capital","maximum_portfolio_exposure_pct","maximum_loss_contribution_pct","maximum_capital_weight_pct","maximum_loss_concentration_score"):
            value=getattr(self,name)
            if value < 0.0: raise ValueError(f"{name} must be non-negative")
