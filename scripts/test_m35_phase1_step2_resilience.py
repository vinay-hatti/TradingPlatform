from datetime import datetime, timezone
from trading_ai.scanner.universe_management import ProviderFetchResult, SecurityProfile, UniverseReconciliationService

class Good:
    name = "GOOD"
    def fetch(self):
        return ProviderFetchResult(self.name, (SecurityProfile("AAPL", exchange="NASDAQ", source=self.name),), datetime.now(timezone.utc))

class Bad:
    name = "BAD"
    def fetch(self):
        raise RuntimeError("simulated SSL failure")


def main():
    result = UniverseReconciliationService().fetch_and_reconcile([Bad(), Good()])
    assert len(result.securities) == 1
    assert result.failed_provider_count == 1
    assert result.governance_status == "DEGRADED"
    assert any(not item.success and item.error_type == "RuntimeError" for item in result.provider_results)
    print("Step 2 provider isolation assertions passed.")

if __name__ == "__main__": main()
