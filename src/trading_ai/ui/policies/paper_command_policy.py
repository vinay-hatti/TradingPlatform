from __future__ import annotations

from dataclasses import dataclass

from trading_ai.ui.models.paper_commands import GovernedActor


@dataclass(frozen=True)
class PaperCommandLimits:
    max_order_quantity: int = 1000
    max_order_notional: float = 100000.0
    allowed_environments: tuple[str, ...] = ("PAPER", "SIMULATION")


class PaperCommandPolicy:
    SUBMIT_PERMISSION = "paper_orders.submit"
    CANCEL_PERMISSION = "paper_orders.cancel"
    REPLACE_PERMISSION = "paper_orders.replace"
    VIEW_PERMISSION = "paper_orders.view"

    def __init__(self, limits: PaperCommandLimits | None = None):
        self.limits = limits or PaperCommandLimits()

    @staticmethod
    def _has_permission(actor: GovernedActor, permission: str) -> bool:
        permissions = set(actor.permissions)
        roles = {role.upper() for role in actor.roles}
        return (
            permission in permissions
            or "paper_orders.*" in permissions
            or "*" in permissions
            or "ADMIN" in roles
            or "TRADER" in roles
        )

    def authorize(
        self,
        *,
        action: str,
        environment: str,
        actor: GovernedActor,
        confirmation_token: str,
        quantity: int | None = None,
        estimated_price: float | None = None,
    ) -> list[str]:
        reasons: list[str] = []

        if environment not in self.limits.allowed_environments:
            reasons.append(
                "Only PAPER and SIMULATION environments are allowed."
            )

        permission = {
            "SUBMIT": self.SUBMIT_PERMISSION,
            "CANCEL": self.CANCEL_PERMISSION,
            "REPLACE": self.REPLACE_PERMISSION,
            "VIEW": self.VIEW_PERMISSION,
        }.get(action)

        if not permission or not self._has_permission(actor, permission):
            reasons.append(f"Missing required permission: {permission or action}")

        if not confirmation_token.startswith("CONFIRM-PAPER-"):
            reasons.append(
                "A confirmation token beginning with CONFIRM-PAPER- is required."
            )

        if quantity is not None and quantity > self.limits.max_order_quantity:
            reasons.append(
                f"Quantity exceeds paper limit of "
                f"{self.limits.max_order_quantity}."
            )

        if quantity is not None and estimated_price is not None:
            notional = quantity * estimated_price
            if notional > self.limits.max_order_notional:
                reasons.append(
                    f"Estimated notional ${notional:,.2f} exceeds paper limit "
                    f"of ${self.limits.max_order_notional:,.2f}."
                )

        return reasons
