from datetime import date
from unittest.mock import patch
import pandas as pd
from trading_ai.scanner.market_data_population.yfinance_provider import YFinanceBulkHistoricalProvider


def main():
    sleeps=[]
    calls={"n":0}
    def fake_download(**kwargs):
        calls["n"]+=1
        if calls["n"] < 3:
            import sys
            print("429 too many requests", file=sys.stderr)
            return pd.DataFrame()
        idx=pd.to_datetime(["2026-07-22"])
        cols=pd.MultiIndex.from_product([["AAPL"],["Open","High","Low","Close","Volume"]])
        return pd.DataFrame([[100,101,99,100.5,1000000]], index=idx, columns=cols)
    provider=YFinanceBulkHistoricalProvider(max_retries=3, initial_backoff_seconds=1, max_backoff_seconds=8, jitter_ratio=0, rate_limit_cooldown_seconds=2, circuit_breaker_threshold=5, circuit_breaker_cooldown_seconds=0, sleep=sleeps.append)
    with patch("trading_ai.scanner.market_data_population.yfinance_provider.yf.download", side_effect=fake_download):
        result=provider.fetch_batch(["AAPL"], date(2026,7,1), date(2026,7,23))
    assert len(result["AAPL"]) == 1
    d=provider.diagnostics()
    assert d["rate_limit_events"] == 2
    assert d["retries"] == 2
    assert d["suppressed_log_lines"] >= 2
    assert sleeps == [2,2]
    assert d["status"] == "RECOVERED"
    print("Milestone 43 provider resilience assertions passed.")

if __name__ == "__main__": main()
