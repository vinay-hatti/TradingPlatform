from __future__ import annotations

from datetime import date
import time

from trading_ai.options.live_snapshot import (
    PolygonOptionSnapshotProvider,
)


class FakeProvider(PolygonOptionSnapshotProvider):
    def __init__(self):
        super().__init__(
            api_key="test",
            timeout_seconds=1,
            max_retries=0,
            maximum_pages=2,
            overall_timeout_seconds=3,
            progress=False,
        )
        self.calls = 0

    def _request_json(
        self,
        path_or_url,
        params=None,
        *,
        deadline,
        page_number,
    ):
        self.calls += 1
        return {
            "results": [],
            "next_url": (
                "https://example.invalid/page"
                if page_number < 10
                else None
            ),
        }


def main():
    provider = FakeProvider()
    started = time.monotonic()
    contracts = provider.chain(
        "SPY",
        signal="CALL",
        target_expiration=date(2026, 8, 21),
        target_strike=700.0,
        as_of=date(2026, 7, 18),
    )
    elapsed = time.monotonic() - started

    assert contracts == []
    assert provider.calls == 2
    assert elapsed < 1.0

    print("Pages fetched:", provider.calls)
    print("All bounded option-snapshot assertions passed.")


if __name__ == "__main__":
    main()
