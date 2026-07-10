class ExecutionEstimator:
    """
    Estimates realistic fill prices from quoted bid/ask prices.

    This is intentionally conservative and does not assume every trade
    fills at the midpoint.
    """

    def estimate_capacity(
        self,
        volume: int,
        open_interest: int,
        bid_size: int,
        ask_size: int,
        max_volume_ratio: float,
        max_open_interest_ratio: float,
    ) -> int:
        volume = max(int(volume or 0), 0)
        open_interest = max(int(open_interest or 0), 0)
        bid_size = max(int(bid_size or 0), 0)
        ask_size = max(int(ask_size or 0), 0)

        volume_capacity = int(volume * float(max_volume_ratio))
        oi_capacity = int(open_interest * float(max_open_interest_ratio))

        quote_depth = min(bid_size, ask_size)

        capacities = [
            value
            for value in [
                volume_capacity,
                oi_capacity,
                quote_depth,
            ]
            if value > 0
        ]

        if not capacities:
            return 0

        return max(min(capacities), 0)

    def estimated_fill_fraction(
        self,
        requested_contracts: int,
        estimated_capacity: int,
        spread_pct: float,
    ) -> float:
        requested_contracts = max(int(requested_contracts or 1), 1)
        estimated_capacity = max(int(estimated_capacity or 0), 0)
        spread_pct = max(float(spread_pct or 0.0), 0.0)

        capacity_ratio = (
            estimated_capacity / requested_contracts
            if requested_contracts > 0
            else 0.0
        )

        if capacity_ratio >= 5 and spread_pct <= 0.05:
            return 0.20

        if capacity_ratio >= 3 and spread_pct <= 0.10:
            return 0.30

        if capacity_ratio >= 2 and spread_pct <= 0.15:
            return 0.40

        if capacity_ratio >= 1 and spread_pct <= 0.25:
            return 0.55

        if capacity_ratio >= 1:
            return 0.70

        return 0.90

    def estimate_buy_price(
        self,
        bid: float,
        ask: float,
        requested_contracts: int,
        estimated_capacity: int,
        spread_pct: float,
    ) -> float:
        bid = float(bid or 0.0)
        ask = float(ask or 0.0)

        if ask <= 0:
            return 0.0

        if bid <= 0:
            return ask

        fraction = self.estimated_fill_fraction(
            requested_contracts=requested_contracts,
            estimated_capacity=estimated_capacity,
            spread_pct=spread_pct,
        )

        return round(bid + (ask - bid) * fraction, 4)

    def estimate_sell_price(
        self,
        bid: float,
        ask: float,
        requested_contracts: int,
        estimated_capacity: int,
        spread_pct: float,
    ) -> float:
        bid = float(bid or 0.0)
        ask = float(ask or 0.0)

        if bid <= 0:
            return 0.0

        if ask <= bid:
            return bid

        fraction = self.estimated_fill_fraction(
            requested_contracts=requested_contracts,
            estimated_capacity=estimated_capacity,
            spread_pct=spread_pct,
        )

        return round(ask - (ask - bid) * fraction, 4)

    def round_trip_slippage(
        self,
        mid: float,
        estimated_buy_price: float,
        estimated_sell_price: float,
        contracts: int,
    ) -> tuple[float, float]:
        mid = float(mid or 0.0)
        estimated_buy_price = float(estimated_buy_price or 0.0)
        estimated_sell_price = float(estimated_sell_price or 0.0)
        contracts = max(int(contracts or 1), 1)

        if mid <= 0:
            return 0.0, 0.0

        entry_slippage = max(estimated_buy_price - mid, 0.0)
        exit_slippage = max(mid - estimated_sell_price, 0.0)

        per_contract = entry_slippage + exit_slippage
        dollars = per_contract * contracts * 100.0
        pct = per_contract / mid

        return round(dollars, 2), round(pct, 4)
