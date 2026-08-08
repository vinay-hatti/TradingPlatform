from trading_ai.option_valuation_intelligence.events.sources import _bls_from_ical


def test_bls_ical_normalizes_governed_releases_and_uses_uid():
    payload = """BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:empsit-20260904@bls.gov\r\nDTSTART;TZID=America/New_York:20260904T083000\r\nSUMMARY:Employment Situation for August 2026\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:cpi-20260911@bls.gov\r\nDTSTART;TZID=America/New_York:20260911T083000\r\nSUMMARY:Consumer Price Index for August 2026\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"""
    records = _bls_from_ical(payload)
    assert len(records) == 2
    employment = next(r for r in records if r.event_type == "EMPLOYMENT_SITUATION")
    assert employment.source_event_key == "BLS:empsit-20260904@bls.gov"
    assert employment.event_time.isoformat() == "08:30:00"
    assert "NONFARM_PAYROLLS" in employment.event_components


def test_bls_ical_is_deterministically_deduplicated():
    event = """BEGIN:VEVENT\nUID:cpi-20260911@bls.gov\nDTSTART:20260911T083000\nSUMMARY:Consumer Price Index for August 2026\nEND:VEVENT\n"""
    records = _bls_from_ical("BEGIN:VCALENDAR\n" + event + event + "END:VCALENDAR\n")
    assert len(records) == 1
