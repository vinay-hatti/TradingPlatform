class StrategyCatalog:
    SINGLE_LEG = {
        "LONG_CALL",
        "LONG_PUT",
    }

    VERTICAL_SPREADS = {
        "BULL_CALL_SPREAD",
        "BEAR_PUT_SPREAD",
        "BULL_PUT_SPREAD",
        "BEAR_CALL_SPREAD",
    }

    NEUTRAL_SAME_EXPIRY = {
        "IRON_CONDOR",
        "IRON_BUTTERFLY",
        "LONG_STRADDLE",
        "LONG_STRANGLE",
    }

    MULTI_EXPIRATION = {
        "CALENDAR_CALL",
        "CALENDAR_PUT",
        "DIAGONAL_CALL",
        "DIAGONAL_PUT",
    }

    SUPPORTED = (
        SINGLE_LEG
        | VERTICAL_SPREADS
        | NEUTRAL_SAME_EXPIRY
        | MULTI_EXPIRATION
    )

    @classmethod
    def is_supported(
        cls,
        strategy: str,
    ) -> bool:
        return (
            str(strategy or "").upper()
            in cls.SUPPORTED
        )

    @classmethod
    def requires_same_expiry(
        cls,
        strategy: str,
    ) -> bool:
        return (
            str(strategy or "").upper()
            not in cls.MULTI_EXPIRATION
        )

    @classmethod
    def requires_multiple_expiries(
        cls,
        strategy: str,
    ) -> bool:
        return (
            str(strategy or "").upper()
            in cls.MULTI_EXPIRATION
        )

    @classmethod
    def default_direction(
        cls,
        strategy: str,
    ) -> str:
        strategy = str(
            strategy or ""
        ).upper()

        if strategy in {
            "LONG_CALL",
            "BULL_CALL_SPREAD",
            "BULL_PUT_SPREAD",
            "DIAGONAL_CALL",
        }:
            return "CALL"

        if strategy in {
            "LONG_PUT",
            "BEAR_PUT_SPREAD",
            "BEAR_CALL_SPREAD",
            "DIAGONAL_PUT",
        }:
            return "PUT"

        return "NEUTRAL"

    @classmethod
    def default_complexity(
        cls,
        strategy: str,
    ) -> str:
        strategy = str(
            strategy or ""
        ).upper()

        if strategy in cls.SINGLE_LEG:
            return "STANDARD"

        if strategy in cls.VERTICAL_SPREADS:
            return "MULTI_LEG"

        return "COMPLEX"
