from __future__ import annotations
from .portfolio_risk_policy import PortfolioRiskPolicy
from .portfolio_risk_profile import PortfolioExposureProfile, PortfolioRiskCheck, PortfolioSnapshotProfile

class PositionLimitEngine:
    def __init__(self, policy: PortfolioRiskPolicy | None = None) -> None:
        self.policy = policy or PortfolioRiskPolicy()
        self.policy.validate()

    def checks(self, exposure: PortfolioExposureProfile, snapshot: PortfolioSnapshotProfile) -> tuple[PortfolioRiskCheck, ...]:
        checks = []
        limits_by_symbol = {limit.symbol: limit for limit in snapshot.position_limits}
        def add(name, passed, message, metadata=None):
            checks.append(PortfolioRiskCheck(
                name=name, passed=bool(passed), required=True,
                score=100.0 if passed else 0.0,
                severity="LOW" if passed else "CRITICAL",
                message=message, metadata=metadata or {},
            ))

        for profile in exposure.symbols:
            limit = limits_by_symbol.get(profile.symbol)
            if limit is not None:
                quantity = profile.projected_quantity
                if limit.maximum_absolute_quantity is not None:
                    add(
                        f"position_absolute_limit:{profile.symbol}",
                        abs(quantity) <= limit.maximum_absolute_quantity,
                        "Projected absolute position is within symbol limit.",
                        {"projected_quantity": quantity, "limit": limit.maximum_absolute_quantity},
                    )
                if limit.maximum_long_quantity is not None:
                    add(
                        f"position_long_limit:{profile.symbol}",
                        quantity <= limit.maximum_long_quantity,
                        "Projected long position is within symbol limit.",
                    )
                if limit.maximum_short_quantity is not None:
                    add(
                        f"position_short_limit:{profile.symbol}",
                        quantity >= -abs(limit.maximum_short_quantity),
                        "Projected short position is within symbol limit.",
                    )
                if limit.maximum_notional is not None:
                    add(
                        f"position_notional_limit:{profile.symbol}",
                        abs(profile.projected_exposure) <= limit.maximum_notional,
                        "Projected symbol notional is within limit.",
                    )

            if profile.asset_class == "EQUITY":
                add(
                    f"default_equity_position_limit:{profile.symbol}",
                    abs(profile.projected_quantity) <= self.policy.maximum_position_quantity_equity,
                    "Projected equity position is within default limit.",
                )
            elif profile.asset_class == "OPTION":
                add(
                    f"default_option_position_limit:{profile.symbol}",
                    abs(profile.projected_quantity) <= self.policy.maximum_position_contracts_option,
                    "Projected option position is within default limit.",
                )
        return tuple(checks)
