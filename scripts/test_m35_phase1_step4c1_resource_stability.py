from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile

import pandas as pd

from trading_ai.scanner.market_data_population.resource_lifecycle import snapshot_resources
from trading_ai.scanner.market_data_population.serialization import write_json_atomic
from trading_ai.scanner.market_data_population.yfinance_provider import YFinanceBulkHistoricalProvider
import trading_ai.scanner.market_data_population.yfinance_provider as provider_module


def main() -> None:
    calls: list[dict] = []
    original_download = provider_module.yf.download

    def fake_download(**kwargs):
        calls.append(kwargs)
        symbols = list(kwargs['tickers'])
        columns = pd.MultiIndex.from_product([symbols, ['Open', 'High', 'Low', 'Close', 'Volume']])
        values = [[10.0, 11.0, 9.0, 10.5, 100000.0] * len(symbols)]
        return pd.DataFrame(values, index=pd.to_datetime(['2026-07-01']), columns=columns)

    try:
        provider_module.yf.download = fake_download
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            provider = YFinanceBulkHistoricalProvider(
                cache_dir=root / 'yf-cache', provider_chunk_size=3, timeout_seconds=12,
            )
            output = provider.fetch_batch(
                ['AAA', 'BBB', 'CCC', 'DDD', 'EEE', 'FFF', 'GGG'],
                date(2026, 6, 1), date(2026, 7, 2),
            )
            assert len(calls) == 3, calls
            assert all(call['threads'] is False for call in calls)
            assert all(len(call['tickers']) <= 3 for call in calls)
            assert all(call['timeout'] == 12 for call in calls)
            assert set(output) == {'AAA', 'BBB', 'CCC', 'DDD', 'EEE', 'FFF', 'GGG'}
            assert (root / 'yf-cache').is_dir()

            before = snapshot_resources().open_file_descriptors
            checkpoint = root / 'checkpoint.json'
            for index in range(250):
                write_json_atomic(checkpoint, {'iteration': index})
            after = snapshot_resources().open_file_descriptors
            if before is not None and after is not None:
                assert after - before < 5, (before, after)
    finally:
        provider_module.yf.download = original_download

    print('M35 Phase 1 Step 4C.1 resource-stability assertions passed.')


if __name__ == '__main__':
    main()
