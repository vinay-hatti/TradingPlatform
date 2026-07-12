import math

import numpy as np

from trading_ai.strategy_engine.probability_policy import (
    ProbabilityPolicy,
)


class TerminalPriceModel:
    """
    Generates terminal underlying prices using geometric Brownian motion.

    When use_risk_neutral_drift is enabled, drift is:

        risk_free_rate - dividend_yield

    Otherwise, callers can provide an expected annual return.
    """

    def __init__(
        self,
        policy: ProbabilityPolicy | None = None,
    ):
        self.policy = policy or ProbabilityPolicy()
        self.policy.validate()

    def simulate_terminal_prices(
        self,
        underlying_price: float,
        volatility: float,
        horizon_days: int,
        simulation_count: int | None = None,
        random_seed: int | None = None,
        expected_annual_return: float | None = None,
    ) -> np.ndarray:
        price = float(underlying_price)
        sigma = self._normalize_volatility(volatility)
        days = int(horizon_days)

        count = int(
            simulation_count
            if simulation_count is not None
            else self.policy.simulation_count
        )

        seed = int(
            random_seed
            if random_seed is not None
            else self.policy.random_seed
        )

        if price <= 0:
            raise ValueError(
                "underlying_price must be greater than zero"
            )

        if days <= 0:
            raise ValueError(
                "horizon_days must be greater than zero"
            )

        if sigma < self.policy.minimum_volatility:
            raise ValueError(
                "volatility is below the configured minimum"
            )

        if sigma > self.policy.maximum_volatility:
            raise ValueError(
                "volatility exceeds the configured maximum"
            )

        if count < self.policy.minimum_simulations:
            raise ValueError(
                "simulation_count is below the configured minimum"
            )

        if count > self.policy.maximum_simulations:
            raise ValueError(
                "simulation_count exceeds the configured maximum"
            )

        years = days / self.policy.annual_calendar_days

        if self.policy.use_risk_neutral_drift:
            drift_rate = (
                self.policy.risk_free_rate
                - self.policy.dividend_yield
            )
        else:
            drift_rate = float(
                expected_annual_return or 0.0
            )

        drift = (
            drift_rate
            - 0.5 * sigma * sigma
        ) * years

        diffusion_scale = sigma * math.sqrt(years)

        rng = np.random.default_rng(seed)
        normal_draws = rng.standard_normal(count)

        terminal_prices = price * np.exp(
            drift + diffusion_scale * normal_draws
        )

        return terminal_prices

    def simulate_paths(
        self,
        underlying_price: float,
        volatility: float,
        horizon_days: int,
        simulation_count: int | None = None,
        random_seed: int | None = None,
    ) -> np.ndarray:
        price = float(underlying_price)
        sigma = self._normalize_volatility(volatility)
        days = int(horizon_days)

        count = int(
            simulation_count
            if simulation_count is not None
            else self.policy.simulation_count
        )

        seed = int(
            random_seed
            if random_seed is not None
            else self.policy.random_seed
        )

        if price <= 0 or sigma <= 0 or days <= 0:
            raise ValueError(
                "price, volatility, and horizon_days must be positive"
            )

        dt = 1.0 / self.policy.annual_calendar_days

        drift_rate = (
            self.policy.risk_free_rate
            - self.policy.dividend_yield
        )

        daily_drift = (
            drift_rate - 0.5 * sigma * sigma
        ) * dt

        daily_diffusion = sigma * math.sqrt(dt)

        rng = np.random.default_rng(seed)

        shocks = rng.standard_normal(
            size=(count, days)
        )

        log_returns = (
            daily_drift
            + daily_diffusion * shocks
        )

        log_paths = np.cumsum(
            log_returns,
            axis=1,
        )

        initial_column = np.full(
            shape=(count, 1),
            fill_value=price,
        )

        simulated = price * np.exp(log_paths)

        return np.concatenate(
            [initial_column, simulated],
            axis=1,
        )

    def _normalize_volatility(
        self,
        value: float,
    ) -> float:
        volatility = float(value or 0.0)

        if volatility > 3.0:
            volatility /= 100.0

        return volatility
