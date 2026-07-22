from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from .universe_profile import SecurityProfile


@dataclass(frozen=True)
class ProviderFetchResult:
    provider_name: str
    securities: tuple[SecurityProfile, ...]
    fetched_at: datetime
    success: bool = True
    from_cache: bool = False
    source_uri: str = ""
    warning: str = ""
    error_type: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class UniverseProviderResult:
    """Backward-compatible Step-2 provider result.

    The original public API used positional ordering
    ``(provider_name, fetched_at, securities)``.  Keep that contract while the
    newer internal ``ProviderFetchResult`` continues to use its existing field
    ordering.
    """

    provider_name: str
    fetched_at: datetime
    securities: tuple[SecurityProfile, ...]
    success: bool = True
    from_cache: bool = False
    source_uri: str = ""
    warning: str = ""
    error_type: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

    def to_provider_fetch_result(self) -> ProviderFetchResult:
        return ProviderFetchResult(
            provider_name=self.provider_name,
            securities=self.securities,
            fetched_at=self.fetched_at,
            success=self.success,
            from_cache=self.from_cache,
            source_uri=self.source_uri,
            warning=self.warning,
            error_type=self.error_type,
            metadata=dict(self.metadata),
        )


class UniverseProvider(Protocol):
    @property
    def name(self) -> str: ...

    def fetch(self) -> ProviderFetchResult: ...
