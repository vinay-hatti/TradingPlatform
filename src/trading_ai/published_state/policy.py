from __future__ import annotations

from dataclasses import dataclass

from .governance import PublishedStateConsumer


@dataclass(frozen=True)
class PublishedStatePolicy:
    publication_name: str = "current_market_state"
    maximum_age_seconds: int = 36 * 60 * 60
    warning_age_seconds: int | None = 24 * 60 * 60
    allow_degraded: bool = True
    require_option_snapshot: bool = True
    require_option_snapshot_timestamp: bool = True
    require_market_intelligence_timestamp: bool = True
    require_scanner_ready: bool = False
    require_decision_context_ready: bool = False
    consumer: str = PublishedStateConsumer.GENERIC.value

    def validate(self) -> None:
        if not self.publication_name.strip():
            raise ValueError("publication_name must not be blank")
        if self.maximum_age_seconds <= 0:
            raise ValueError("maximum_age_seconds must be positive")
        if self.warning_age_seconds is not None:
            if self.warning_age_seconds <= 0:
                raise ValueError("warning_age_seconds must be positive when provided")
        if self.consumer not in {item.value for item in PublishedStateConsumer}:
            raise ValueError(f"Unsupported published-state consumer: {self.consumer}")

    @classmethod
    def for_consumer(
        cls,
        consumer: str | PublishedStateConsumer,
        *,
        publication_name: str = "current_market_state",
        maximum_age_seconds: int = 36 * 60 * 60,
        warning_age_seconds: int | None = 24 * 60 * 60,
        allow_degraded: bool = True,
    ) -> "PublishedStatePolicy":
        value = consumer.value if isinstance(consumer, PublishedStateConsumer) else str(consumer).lower()
        if value == PublishedStateConsumer.SCANNER.value:
            return cls(
                publication_name=publication_name,
                maximum_age_seconds=maximum_age_seconds,
                warning_age_seconds=warning_age_seconds,
                allow_degraded=allow_degraded,
                require_scanner_ready=True,
                require_decision_context_ready=False,
                consumer=value,
            )
        if value == PublishedStateConsumer.DECISION.value:
            return cls(
                publication_name=publication_name,
                maximum_age_seconds=maximum_age_seconds,
                warning_age_seconds=warning_age_seconds,
                allow_degraded=allow_degraded,
                require_scanner_ready=False,
                require_decision_context_ready=True,
                consumer=value,
            )
        if value == PublishedStateConsumer.GENERIC.value:
            return cls(
                publication_name=publication_name,
                maximum_age_seconds=maximum_age_seconds,
                warning_age_seconds=warning_age_seconds,
                allow_degraded=allow_degraded,
                consumer=value,
            )
        raise ValueError(f"Unsupported published-state consumer: {consumer}")
