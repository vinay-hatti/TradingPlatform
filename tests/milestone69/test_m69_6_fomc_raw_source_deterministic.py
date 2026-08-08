from datetime import date
import importlib.util
from pathlib import Path

P = Path(__file__).resolve().parents[2] / 'scripts' / 'backfill_m69_historical_macro_events.py'
spec = importlib.util.spec_from_file_location('m696raw', P); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)


def test_historical_heading_parser_excludes_nonmeetings(monkeypatch):
    monkeypatch.setattr(mod, 'date', type('D',(date,),{'today':classmethod(lambda cls: cls(2026,8,6))}))
    html='''<h5>January 26-27 Meeting - 2016</h5><div>Statement</div><h5>March 1 Notation Vote - 2016</h5><h5>April 1 Meeting - 2016 (cancelled)</h5>'''
    rows=mod._parse_historical_fomc_year(2016,html)
    assert [r[2] for r in rows]==['2016-01-27']


def test_consolidated_calendar_completed_and_future(monkeypatch):
    monkeypatch.setattr(mod, 'date', type('D',(date,),{'today':classmethod(lambda cls: cls(2026,8,6))}))
    html='''<h4>2026 FOMC Meetings</h4><div>June</div><div>16-17*</div><div>Statement:</div><a>HTML</a><div>July</div><div>28-29</div><div>Statement:</div><a>HTML</a><div>August</div><div>22 (notation vote)</div><div>Statement on Longer-Run Goals</div><div>September</div><div>15-16*</div><div>October</div><div>27-28</div><h4>2027 FOMC Meetings</h4><div>January</div><div>26-27</div>'''
    rows=mod._parse_consolidated_fomc_calendar(2016,html)
    assert [r[2] for r in rows]==['2026-06-17','2026-07-29','2026-09-16','2026-10-28','2027-01-27']
    assert 'SCHEDULED_MEETING' in rows[-1][6]


def test_calendar_parser_handles_cross_month_ranges(monkeypatch):
    monkeypatch.setattr(mod, 'date', type('D',(date,),{'today':classmethod(lambda cls: cls(2026,8,6))}))
    html='''<h4>2024 FOMC Meetings</h4><div>Apr/May</div><div>30-1</div><div>Statement:</div><a>HTML</a><div>Oct/Nov</div><div>31-1</div><div>Statement:</div><a>HTML</a>'''
    rows=mod._parse_consolidated_fomc_calendar(2016,html)
    assert [r[2] for r in rows]==['2024-05-01','2024-11-01']
