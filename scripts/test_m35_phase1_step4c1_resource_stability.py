from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
import tempfile

from trading_ai.scanner.market_data_population.resource_lifecycle import snapshot_resources
from trading_ai.scanner.market_data_population.serialization import write_json_atomic
from trading_ai.scanner.market_data_population.polygon_provider import PolygonBulkHistoricalProvider


class FakeHistoricalProvider:
    def __init__(self): self.calls=[]
    def fetch_history(self, symbol, start, end):
        self.calls.append((symbol,start,end))
        return [SimpleNamespace(symbol=symbol,time=1782864000000,open=10,high=11,low=9,close=10.5,volume=100000)]


def main() -> None:
    fake=FakeHistoricalProvider()
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        provider=PolygonBulkHistoricalProvider(historical_provider=fake)
        output=provider.fetch_batch(['AAA','BBB','CCC','DDD','EEE','FFF','GGG'], date(2026,6,1), date(2026,7,2))
        assert len(fake.calls)==7
        assert set(output)=={'AAA','BBB','CCC','DDD','EEE','FFF','GGG'}
        before=snapshot_resources().open_file_descriptors
        checkpoint=root/'checkpoint.json'
        for index in range(250): write_json_atomic(checkpoint, {'iteration':index})
        after=snapshot_resources().open_file_descriptors
        if before is not None and after is not None: assert after-before<5,(before,after)
    print('M35 Phase 1 Step 4C.1 Polygon resource-stability assertions passed.')

if __name__=='__main__': main()
