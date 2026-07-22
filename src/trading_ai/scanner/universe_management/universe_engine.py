from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .universe_policy import UniversePolicy
from .universe_profile import SecurityProfile, UniverseBuildResult, UniverseProfile


class UniverseEngine:
    def __init__(self, policy: UniversePolicy | None = None) -> None:
        self.policy = policy or UniversePolicy()
        self.policy.validate()

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        return str(symbol or "").strip().upper().replace(" ", "")

    @staticmethod
    def _normalize_text(value: str) -> str:
        return str(value or "").strip().upper()

    def build(
        self,
        securities: Iterable[SecurityProfile],
        *,
        universe_id: str = "US-LISTED-PRIMARY",
        name: str = "US Listed Equity and ETF Universe",
        generated_at: datetime | None = None,
    ) -> UniverseBuildResult:
        accepted: list[SecurityProfile] = []
        seen: set[str] = set()
        sources: set[str] = set()
        rejection_reasons: dict[str, int] = {}
        received_count = 0
        duplicate_count = 0

        def reject(reason: str) -> None:
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

        for security in securities:
            received_count += 1
            symbol = self._normalize_symbol(security.symbol)
            exchange = self._normalize_text(security.exchange)
            asset_type = self._normalize_text(security.asset_type)
            source = self._normalize_text(security.source) or "UNKNOWN"

            if not symbol:
                reject("BLANK_SYMBOL")
                continue
            if symbol in seen:
                duplicate_count += 1
                if self.policy.reject_duplicate_symbols:
                    reject("DUPLICATE_SYMBOL")
                    continue
            if asset_type not in self.policy.allowed_asset_types:
                reject("ASSET_TYPE_NOT_ALLOWED")
                continue
            if exchange not in self.policy.allowed_exchanges:
                reject("EXCHANGE_NOT_ALLOWED")
                continue
            if self.policy.require_active and not security.active:
                reject("INACTIVE")
                continue
            if self.policy.require_tradable and not security.tradable:
                reject("NOT_TRADABLE")
                continue

            accepted.append(
                SecurityProfile(
                    symbol=symbol,
                    name=security.name.strip(),
                    exchange=exchange,
                    asset_type=asset_type,
                    active=security.active,
                    tradable=security.tradable,
                    options_eligible=security.options_eligible,
                    sector=security.sector.strip(),
                    industry=security.industry.strip(),
                    market_cap=security.market_cap,
                    average_daily_volume=security.average_daily_volume,
                    source=source,
                    metadata=dict(security.metadata),
                )
            )
            seen.add(symbol)
            sources.add(source)

        accepted.sort(key=lambda item: item.symbol)
        warnings: list[str] = []
        if len(accepted) < self.policy.minimum_symbol_count:
            warnings.append(
                f"Accepted universe contains {len(accepted)} symbols; "
                f"minimum required is {self.policy.minimum_symbol_count}."
            )

        governance_status = "READY" if not warnings else "REVIEW"
        universe = UniverseProfile(
            universe_id=universe_id,
            name=name,
            generated_at=generated_at or datetime.now(timezone.utc),
            securities=tuple(accepted),
            source_names=tuple(sorted(sources)),
            governance_status=governance_status,
            warnings=tuple(warnings),
            metadata={
                "minimum_symbol_count": self.policy.minimum_symbol_count,
                "options_eligible_count": sum(
                    1 for security in accepted if security.options_eligible
                ),
            },
        )
        return UniverseBuildResult(
            universe=universe,
            received_count=received_count,
            accepted_count=len(accepted),
            rejected_count=received_count - len(accepted),
            duplicate_count=duplicate_count,
            rejection_reasons=dict(sorted(rejection_reasons.items())),
        )
