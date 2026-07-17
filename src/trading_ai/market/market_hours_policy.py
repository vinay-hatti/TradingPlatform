from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketHoursPolicy:
    timezone: str = "America/New_York"
    regular_open: str = "09:30"
    regular_close: str = "16:00"
    premarket_open: str = "04:00"
    afterhours_close: str = "20:00"
    weekdays: tuple[int, ...] = (0, 1, 2, 3, 4)
    observe_holidays: bool = True
    allow_premarket: bool = True
    allow_afterhours: bool = True
    reject_closed_market_events: bool = False

    def validate(self) -> None:
        for name in (
            "regular_open",
            "regular_close",
            "premarket_open",
            "afterhours_close",
        ):
            value = getattr(self, name)
            parts = value.split(":")
            if len(parts) != 2:
                raise ValueError(f"{name} must use HH:MM format")
            hour, minute = int(parts[0]), int(parts[1])
            if not 0 <= hour <= 23 or not 0 <= minute <= 59:
                raise ValueError(f"{name} contains an invalid time")
        if not self.weekdays:
            raise ValueError("weekdays cannot be empty")
