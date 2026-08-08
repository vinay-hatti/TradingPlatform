from datetime import date
import importlib.util
from pathlib import Path
import sys, types

# Isolate parser tests from the project database package.
trading_ai = types.ModuleType('trading_ai')
database = types.ModuleType('trading_ai.database')
session = types.ModuleType('trading_ai.database.session')
session.SessionLocal = object
sys.modules.setdefault('trading_ai', trading_ai)
sys.modules.setdefault('trading_ai.database', database)
sys.modules.setdefault('trading_ai.database.session', session)

SCRIPT = Path(__file__).parents[2] / 'scripts' / 'backfill_m69_historical_macro_events.py'
spec = importlib.util.spec_from_file_location('macro_backfill', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_historical_parser_requires_statement_and_excludes_nonmeetings(monkeypatch):
    monkeypatch.setattr(mod, 'date', type('D', (), {'today': staticmethod(lambda: date(2020, 12, 31))}))
    html = '''
      <h5>January 28-29 Meeting - 2020</h5><div>Statement</div>
      <h5>March 2 (unscheduled) Meeting - 2020</h5><div>Statement (Released March 3)</div>
      <h5>March 17-18 (cancelled) Meeting - 2020</h5><div></div>
      <h5>March 19 (notation vote) - 2020</h5><div>Press Release</div>
      <h5>April 28-29 Meeting - 2020</h5><div>Minutes only</div>
    '''
    rows = mod._parse_historical_fomc_year(2020, html)
    assert [row[2] for row in rows] == ['2020-01-29', '2020-03-02']
    assert 'UNSCHEDULED_MEETING' in rows[1][6]


def test_consolidated_parser_uses_statement_link_date_only(monkeypatch):
    monkeypatch.setattr(mod, 'date', type('D', (), {'today': staticmethod(lambda: date(2021, 12, 31))}))
    html = '''
      <h4>2021 FOMC Meetings</h4>
      <div>January 26-27 Statement: <a href="/newsevents/pressreleases/monetary20210127a.htm">HTML</a>
      Minutes: <a href="/newsevents/pressreleases/monetary20210217a.htm">HTML</a></div>
      <div>March 16-17 Statement: <a href="/newsevents/pressreleases/monetary20210317a1.htm">HTML</a></div>
      <h4>2022 FOMC Meetings</h4>
      <div>January 25-26 Statement: <a href="/newsevents/pressreleases/monetary20220126a.htm">HTML</a></div>
    '''
    rows = mod._parse_consolidated_fomc_calendar(2021, html)
    assert [row[2] for row in rows] == ['2021-01-27', '2021-03-17']


def test_no_loose_month_day_calendar_regex_remains():
    source = SCRIPT.read_text()
    assert 'policy-statement links' in source
    assert "statement_pattern" in source
    assert "Meeting\\s*[-–—]" in source


def test_reconciliation_does_not_invalidate_future_active_fomc():
    source = (Path(__file__).parents[2] / 'scripts' / 'reconcile_m69_macro_event_integrity.py').read_text()
    assert "SUBSTRING(event_date FROM 1 FOR 10)::date<=CURRENT_DATE" in source
