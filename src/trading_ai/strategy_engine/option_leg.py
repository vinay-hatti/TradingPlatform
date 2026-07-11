from dataclasses import dataclass


@dataclass
class OptionLeg:
    symbol: str
    option_symbol: str

    option_type: str
    action: str

    strike: float
    expiry: str

    quantity: int
    premium: float

    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0

    implied_volatility: float = 0.0

    bid: float = 0.0
    ask: float = 0.0
    mid: float = 0.0

    volume: int = 0
    open_interest: int = 0

    def __post_init__(self):
        self.symbol = str(self.symbol or "").upper()
        self.option_symbol = str(self.option_symbol or "")

        self.option_type = str(
            self.option_type or ""
        ).upper()

        self.action = str(
            self.action or ""
        ).upper()

        self.strike = float(self.strike or 0.0)
        self.expiry = str(self.expiry or "")

        self.quantity = max(
            int(self.quantity or 1),
            1,
        )

        self.premium = float(
            self.premium or 0.0
        )

        if self.option_type not in {
            "CALL",
            "PUT",
        }:
            raise ValueError(
                f"Invalid option_type: {self.option_type}"
            )

        if self.action not in {
            "BUY",
            "SELL",
            "LONG",
            "SHORT",
        }:
            raise ValueError(
                f"Invalid option action: {self.action}"
            )

        if self.strike <= 0:
            raise ValueError(
                "Option strike must be greater than zero"
            )

        if self.premium < 0:
            raise ValueError(
                "Option premium cannot be negative"
            )

    @property
    def normalized_action(self) -> str:
        if self.action in {"BUY", "LONG"}:
            return "BUY"

        return "SELL"

    @property
    def sign(self) -> float:
        return (
            1.0
            if self.normalized_action == "BUY"
            else -1.0
        )

    @property
    def cash_flow_per_share(self) -> float:
        """
        Buying premium is a negative cash flow.
        Selling premium is a positive cash flow.
        """

        if self.normalized_action == "BUY":
            return -self.premium * self.quantity

        return self.premium * self.quantity

    @property
    def cash_flow_dollars(self) -> float:
        return self.cash_flow_per_share * 100.0

    def intrinsic_value(
        self,
        underlying_price: float,
    ) -> float:
        price = float(underlying_price or 0.0)

        if self.option_type == "CALL":
            return max(
                price - self.strike,
                0.0,
            )

        return max(
            self.strike - price,
            0.0,
        )

    def expiration_value(
        self,
        underlying_price: float,
    ) -> float:
        intrinsic = self.intrinsic_value(
            underlying_price
        )

        return (
            self.sign
            * intrinsic
            * self.quantity
        )

    def expiration_pnl_per_share(
        self,
        underlying_price: float,
    ) -> float:
        return (
            self.expiration_value(
                underlying_price
            )
            + self.cash_flow_per_share
        )

    def expiration_pnl_dollars(
        self,
        underlying_price: float,
    ) -> float:
        return (
            self.expiration_pnl_per_share(
                underlying_price
            )
            * 100.0
        )
