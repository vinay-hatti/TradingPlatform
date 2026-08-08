from datetime import date
import importlib.util
from pathlib import Path
import sys, types

trading_ai = types.ModuleType('trading_ai')
database = types.ModuleType('trading_ai.database')
session = types.ModuleType('trading_ai.database.session')
session.SessionLocal = object
sys.modules.setdefault('trading_ai', trading_ai)
sys.modules.setdefault('trading_ai.database', database)
sys.modules.setdefault('trading_ai.database.session', session)

SCRIPT = Path(__file__).parents[2] / 'scripts' / 'backfill_m69_historical_macro_events.py'
spec = importlib.util.spec_from_file_location('macro_backfill_split', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_historical_heading_is_primary_and_nonmeetings_are_excluded(monkeypatch):
    monkeypatch.setattr(mod, 'date', type('D', (), {'today': staticmethod(lambda: date(2020, 12, 31))}))
    html = '''
      <h5>January 28-29 Meeting - 2020</h5><div>Minutes only</div>
      <h5>March 2 (unscheduled) Meeting - 2020</h5><div>Statement</div>
      <h5>March 17-18 (cancelled) Meeting - 2020</h5><div>Statement</div>
      <h5>March 19 (notation vote) - 2020</h5><div>Statement</div>
    '''
    rows = mod._parse_historical_fomc_year(2020, html)
    assert [row[2] for row in rows] == ['2020-01-29', '2020-03-02']
    assert 'MEETING_HEADING_BACKED' in rows[0][6]
    assert 'UNSCHEDULED_MEETING' in rows[1][6]


def test_press_release_index_selects_only_canonical_fomc_statement(monkeypatch):
    monkeypatch.setattr(mod, 'date', type('D', (), {'today': staticmethod(lambda: date(2022, 12, 31))}))
    html = '''
      <a href="/newsevents/pressreleases/monetary20220126a.htm">Federal Reserve issues FOMC statement</a>
      <a href="/newsevents/pressreleases/monetary20220126b.htm">Economic projections</a>
      <a href="/newsevents/pressreleases/monetary20220216a.htm">Minutes release</a>
    '''
    rows = mod._parse_press_release_fomc_year(2022, html)
    assert [row[2] for row in rows] == ['2022-01-26']


def test_forward_calendar_restores_future_scheduled_meetings(monkeypatch):
    monkeypatch.setattr(mod, 'date', type('D', (), {'today': staticmethod(lambda: date(2026, 8, 6))}))
    html = '''
      <h4>2026 FOMC Meetings</h4>
      <div>September 15-16*</div><div>October 27-28</div><div>December 8-9*</div>
      <h4>2027 FOMC Meetings</h4>
      <div>January 26-27</div><div>March 16-17*</div>
    '''
    rows = mod._parse_forward_fomc_calendar(2016, html)
    assert [row[2] for row in rows] == ['2026-09-16', '2026-10-28', '2026-12-09', '2027-01-27', '2027-03-17']
    assert all('SCHEDULED_MEETING' in row[6] for row in rows)


def test_reconciliation_has_separate_completed_and_future_sets():
    source = (Path(__file__).parents[2] / 'scripts' / 'reconcile_m69_macro_event_integrity.py').read_text()
    assert 'valid_completed_fed' in source
    assert 'valid_future_fed' in source
    assert 'authoritative_future_fomc_dates' in source
