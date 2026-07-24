from datetime import date
from pydantic import ValidationError
from trading_ai.daily_scan_workstation.models import DailyScanRequest, DataRefreshRequest, RefreshMode

request=DailyScanRequest(symbols=['AAPL','MSFT'],minimum_score=65,top=5,refresh_mode=RefreshMode.REFRESH_MISSING,auto_refresh=True)
assert request.top==5 and request.minimum_score==65
assert request.refresh_mode is RefreshMode.REFRESH_MISSING and request.auto_refresh is True
assert request.minimum_refresh_coverage_pct == 98.0
assert request.maximum_failed_refresh_symbols == 10
assert request.continue_on_degraded_refresh is True
refresh=DataRefreshRequest(symbols=['AAPL'],refresh_mode='cache_only')
assert refresh.refresh_mode is RefreshMode.CACHE_ONLY
assert refresh.minimum_coverage_pct == 98.0
assert refresh.maximum_failed_symbols == 10
assert refresh.max_retries == 3
try:
    DailyScanRequest(start=date(2026,7,22),end=date(2026,1,1))
except ValidationError:
    pass
else:
    raise AssertionError('invalid date range accepted')
print('Milestone 43 request governance assertions passed.')
