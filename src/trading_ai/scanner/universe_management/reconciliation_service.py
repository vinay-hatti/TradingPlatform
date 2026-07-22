from __future__ import annotations
from datetime import datetime, timezone

from .provider_contracts import ProviderFetchResult
from .reconciliation import UniverseReconciliationEngine


class UniverseReconciliationService:
    def __init__(self, engine: UniverseReconciliationEngine | None = None) -> None:
        self.engine = engine or UniverseReconciliationEngine()

    def fetch_and_reconcile(self, providers):
        results = []
        for provider in providers:
            try:
                results.append(provider.fetch())
            except Exception as exc:
                results.append(ProviderFetchResult(
                    provider_name=getattr(provider, "name", provider.__class__.__name__),
                    securities=(),
                    fetched_at=datetime.now(timezone.utc),
                    success=False,
                    warning=str(exc),
                    error_type=exc.__class__.__name__,
                ))
        return self.engine.reconcile(results)
