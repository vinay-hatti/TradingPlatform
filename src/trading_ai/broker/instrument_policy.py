from dataclasses import dataclass

@dataclass(frozen=True)
class InstrumentMappingPolicy:
    allowed_asset_classes: tuple[str, ...] = ("EQUITY", "OPTION")
    allowed_option_types: tuple[str, ...] = ("CALL", "PUT")
    minimum_strike: float = 0.01
    maximum_contract_multiplier: int = 1000
    default_option_multiplier: int = 100
    require_option_expiration: bool = True
    require_option_type: bool = True
    require_option_strike: bool = True
    require_underlying_symbol: bool = True
    reject_expired_options: bool = True

    def validate(self) -> None:
        if not self.allowed_asset_classes:
            raise ValueError("allowed_asset_classes cannot be empty")
        if not self.allowed_option_types:
            raise ValueError("allowed_option_types cannot be empty")
        if self.minimum_strike <= 0:
            raise ValueError("minimum_strike must be positive")
        if self.default_option_multiplier <= 0:
            raise ValueError("default_option_multiplier must be positive")
        if self.maximum_contract_multiplier < self.default_option_multiplier:
            raise ValueError("maximum_contract_multiplier cannot be below default")
