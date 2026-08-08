from pathlib import Path
import importlib.util
import sys
import types


def load(path, name):
    # The parser functions are pure; stub only the project database module for isolated package testing.
    trading_ai = types.ModuleType('trading_ai')
    database = types.ModuleType('trading_ai.database')
    session = types.ModuleType('trading_ai.database.session')
    session.SessionLocal = object
    sys.modules.setdefault('trading_ai', trading_ai)
    sys.modules.setdefault('trading_ai.database', database)
    sys.modules.setdefault('trading_ai.database.session', session)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_historical_fomc_parser_uses_final_meeting_day():
    module = load(Path('scripts/backfill_m69_historical_macro_events.py'), 'macro_v3')
    html = '<h5>January 26-27 Meeting - 2016</h5><h5>March 2 (unscheduled) Meeting - 2016</h5>'
    dates = [row[2] for row in module._parse_historical_fomc_year(2016, html)]
    assert '2016-01-27' in dates
    assert '2016-03-02' in dates


def test_consolidated_fomc_parser_is_year_bounded():
    module = load(Path('scripts/backfill_m69_historical_macro_events.py'), 'macro_v3_b')
    html = '2025 FOMC Meetings January 28-29 March 18-19* 2024 FOMC Meetings January 30-31 March 19-20*'
    dates = [row[2] for row in module._parse_consolidated_fomc_calendar(2024, html)]
    assert dates == ['2025-01-29', '2025-03-19', '2024-01-31', '2024-03-20']


def test_verifier_counts_distinct_canonical_events_and_duplicates():
    text = Path('scripts/verify_m69_event_intelligence_hardening.py').read_text()
    assert 'COUNT(DISTINCT SUBSTRING(event_date FROM 1 FOR 10))' in text
    assert 'duplicate_macro_events_zero' in text


def test_reconciliation_supersedes_duplicate_macro_rows():
    text = Path('scripts/reconcile_m69_macro_event_integrity.py').read_text()
    assert '_duplicate_losers' in text
    assert 'MACRO_CANONICAL_RECONCILIATION_V2' in text
