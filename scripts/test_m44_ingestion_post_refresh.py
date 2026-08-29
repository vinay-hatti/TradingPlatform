from __future__ import annotations
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from trading_ai.institutional_market_structure.refresh import DealerPositionRefreshOrchestrator, write_refresh_profile

class Snapshot:
    option_snapshot_date='2026-07-24'; source_contract_count=100; executable_contract_count=90
    positioning_label='MODERATELY_BULLISH'; confidence_score=.8

class FakeService:
    def __init__(self, policy): self.policy=policy
    def run(self, symbol, as_of, output_dir, persist, write_reports):
        assert persist is True
        if symbol == 'BAD': raise ValueError('No persisted option snapshot')
        if symbol == 'ERR': raise RuntimeError('boom')
        return Snapshot()

def main():
    profile=DealerPositionRefreshOrchestrator(write_reports=False,service_factory=FakeService).run(['SPY','SPY','BAD','ERR'],date(2026,7,24),continue_on_error=True)
    assert profile.requested_symbols == 3
    assert profile.refreshed_symbols == 1
    assert profile.skipped_symbols == 1
    assert profile.failed_symbols == 1
    with TemporaryDirectory() as tmp:
        path=write_refresh_profile(profile,Path(tmp)/'profile.json')
        assert path.exists() and 'REFRESHED' in path.read_text()
    print('Milestone 44 ingestion post-refresh assertions passed.')
if __name__=='__main__': main()
