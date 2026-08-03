from dataclasses import dataclass, field


@dataclass
class SpreadCandidate:
    symbol: str
    strategy: str
    option_type: str

    short_strike: float
    long_strike: float
    expiry: str
    dte: int

    credit_or_debit: float
    width: float
    max_profit: float
    max_loss: float

    short_delta: float
    long_delta: float
    net_delta: float
    net_theta: float
    net_vega: float

    liquidity_score: float
    greek_score: float
    width_score: float
    risk_reward_score: float
    composite_score: float

    reason: str
    allowed: bool = True
    warnings: list[str] = field(default_factory=list)

    # Exact provider contract identities retained end-to-end.
    short_option_symbol: str = ""
    long_option_symbol: str = ""
    short_contract_id: int = 0
    long_contract_id: int = 0

    short_bid: float = 0.0
    short_ask: float = 0.0
    short_last: float = 0.0
    short_mid: float = 0.0
    short_volume: int = 0
    short_open_interest: int = 0
    short_gamma: float = 0.0
    short_theta: float = 0.0
    short_vega: float = 0.0
    short_rho: float = 0.0
    short_implied_volatility: float = 0.0

    long_bid: float = 0.0
    long_ask: float = 0.0
    long_last: float = 0.0
    long_mid: float = 0.0
    long_volume: int = 0
    long_open_interest: int = 0
    long_gamma: float = 0.0
    long_theta: float = 0.0
    long_vega: float = 0.0
    long_rho: float = 0.0
    long_implied_volatility: float = 0.0

    @property
    def option_symbol(self) -> str:
        # Backward-compatible display field; spreads have two identities.
        return self.long_option_symbol or self.short_option_symbol

    @property
    def legs(self) -> list[dict]:
        option_type = str(self.option_type or "").upper()
        strategy = str(self.strategy or "").upper()
        if strategy in {"BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"}:
            long_action, short_action = "BUY", "SELL"
        else:
            short_action, long_action = "SELL", "BUY"
        return [
            {
                "option_symbol": self.long_option_symbol,
                "contract_id": self.long_contract_id,
                "option_type": option_type,
                "action": long_action,
                "side": long_action,
                "quantity": 1,
                "strike": self.long_strike,
                "expiry": self.expiry,
                "premium": self.long_mid,
                "limit_price": self.long_mid,
                "bid": self.long_bid, "ask": self.long_ask, "last": self.long_last,
                "mid": self.long_mid, "volume": self.long_volume,
                "open_interest": self.long_open_interest, "delta": self.long_delta,
                "gamma": self.long_gamma, "theta": self.long_theta,
                "vega": self.long_vega, "rho": self.long_rho,
                "implied_volatility": self.long_implied_volatility,
            },
            {
                "option_symbol": self.short_option_symbol,
                "contract_id": self.short_contract_id,
                "option_type": option_type,
                "action": short_action,
                "side": short_action,
                "quantity": 1,
                "strike": self.short_strike,
                "expiry": self.expiry,
                "premium": self.short_mid,
                "limit_price": self.short_mid,
                "bid": self.short_bid, "ask": self.short_ask, "last": self.short_last,
                "mid": self.short_mid, "volume": self.short_volume,
                "open_interest": self.short_open_interest, "delta": self.short_delta,
                "gamma": self.short_gamma, "theta": self.short_theta,
                "vega": self.short_vega, "rho": self.short_rho,
                "implied_volatility": self.short_implied_volatility,
            },
        ]
