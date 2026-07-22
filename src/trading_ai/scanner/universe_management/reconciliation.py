from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

from .provider_contracts import ProviderFetchResult
from .universe_profile import SecurityProfile


@dataclass(frozen=True)
class ReconciliationResult:
    securities: tuple[SecurityProfile, ...]
    provider_results: tuple[ProviderFetchResult, ...]
    provider_counts: dict[str, int]
    conflict_count: int
    failed_provider_count: int
    governance_status: str
    generated_at: datetime

    @property
    def metadata(self) -> dict[str, object]:
        """Backward-compatible summary metadata used by Step-2 callers."""
        return {
            "unique_symbol_count": len(self.securities),
            "provider_counts": dict(self.provider_counts),
            "conflict_count": self.conflict_count,
            "failed_provider_count": self.failed_provider_count,
            "governance_status": self.governance_status,
            "generated_at": self.generated_at.isoformat(),
        }


class UniverseReconciliationEngine:
    def reconcile(self, results) -> ReconciliationResult:
        results = tuple(results)
        grouped: dict[str, list[SecurityProfile]] = {}
        counts: dict[str, int] = {}
        for result in results:
            counts[result.provider_name] = len(result.securities)
            if not result.success:
                continue
            for security in result.securities:
                symbol = security.symbol.strip().upper()
                if symbol:
                    grouped.setdefault(symbol, []).append(security)
        merged: list[SecurityProfile] = []
        conflicts = 0
        for symbol, items in grouped.items():
            names = {x.name for x in items if x.name}
            exchanges = {x.exchange for x in items if x.exchange}
            asset_types = {x.asset_type for x in items if x.asset_type}
            if len(names) > 1 or len(exchanges) > 1 or len(asset_types) > 1:
                conflicts += 1
            primary = items[0]
            merged.append(SecurityProfile(
                symbol=symbol,
                name=next((x.name for x in items if x.name), primary.name),
                exchange=primary.exchange,
                asset_type=primary.asset_type,
                active=all(x.active for x in items),
                tradable=all(x.tradable for x in items),
                options_eligible=any(x.options_eligible for x in items),
                sector=next((x.sector for x in items if x.sector), ""),
                industry=next((x.industry for x in items if x.industry), ""),
                market_cap=next((x.market_cap for x in items if x.market_cap is not None), None),
                average_daily_volume=next((x.average_daily_volume for x in items if x.average_daily_volume is not None), None),
                source="+".join(sorted({x.source for x in items if x.source})),
            ))
        failed = sum(1 for x in results if not x.success)
        status = "READY" if merged and failed == 0 else ("DEGRADED" if merged else "FAILED")
        return ReconciliationResult(tuple(sorted(merged, key=lambda x: x.symbol)), results, counts, conflicts, failed, status, datetime.now(timezone.utc))
