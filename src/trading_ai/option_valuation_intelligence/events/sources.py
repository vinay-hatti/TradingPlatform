from __future__ import annotations

import csv
import io
import os
import re
import subprocess
from pathlib import Path
from datetime import date, datetime, time
from html import unescape
from urllib.parse import urlencode

import requests

from .contracts import SourceEventRecord
from .policy import EventSyncPolicy

TAG_RE = re.compile(r"<[^>]+>")
ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.I | re.S)

BLS_ICAL_URL = "https://www.bls.gov/schedule/news_release/bls.ics"
BLS_CURRENT_YEAR_URL = "https://www.bls.gov/schedule/news_release/current_year.asp"
SOURCE_FETCH_METADATA: dict[str, dict] = {}


def _text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(TAG_RE.sub(" ", value))).strip()


def _parse_clock(value: str) -> time | None:
    cleaned = value.strip().upper().replace("A.M.", "AM").replace("P.M.", "PM")
    for fmt in ("%I:%M %p", "%I %p", "%H:%M"):
        try:
            return datetime.strptime(cleaned, fmt).time()
        except ValueError:
            pass
    return None


def _request_headers(policy: EventSyncPolicy, *, calendar: bool = False) -> dict[str, str]:
    # BLS blocks some generic script clients. These headers identify a normal,
    # governed HTTPS client while still preserving the configured product token.
    accept = "text/calendar, text/plain;q=0.9, */*;q=0.8" if calendar else (
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    )
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
            f"{policy.user_agent}"
        ),
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.bls.gov/schedule/",
    }


def _http_get(
    url: str,
    policy: EventSyncPolicy,
    *,
    calendar: bool = False,
) -> requests.Response:
    response = requests.get(
        url,
        timeout=policy.timeout_seconds,
        headers=_request_headers(policy, calendar=calendar),
        allow_redirects=True,
    )
    response.raise_for_status()
    return response



def _curl_get_text(url: str, policy: EventSyncPolicy, *, calendar: bool = False) -> str:
    """macOS/system-curl fallback for government sites that reject requests clients."""
    headers = _request_headers(policy, calendar=calendar)
    command = [
        "curl", "-fsSL", "--compressed", "--retry", "2",
        "--connect-timeout", str(min(policy.timeout_seconds, 15)),
        "--max-time", str(policy.timeout_seconds),
    ]
    for name, value in headers.items():
        command.extend(["-H", f"{name}: {value}"])
    command.append(url)
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"curl failed with exit {completed.returncode}")
    return completed.stdout


def alpha_vantage_earnings(
    policy: EventSyncPolicy,
    api_key: str | None = None,
) -> list[SourceEventRecord]:
    key = api_key or os.getenv("ALPHAVANTAGE_API_KEY")
    if not key:
        raise RuntimeError("ALPHAVANTAGE_API_KEY is not configured")
    url = "https://www.alphavantage.co/query?" + urlencode(
        {
            "function": "EARNINGS_CALENDAR",
            "horizon": policy.earnings_horizon,
            "apikey": key,
        }
    )
    text = _http_get(url, policy).text
    rows: list[SourceEventRecord] = []
    for row in csv.DictReader(io.StringIO(text)):
        symbol = (row.get("symbol") or "").strip().upper()
        report = (row.get("reportDate") or "").strip()
        if not symbol or not report:
            continue
        event_date = date.fromisoformat(report)
        session = {
            "pre-market": "PRE_MARKET",
            "post-market": "POST_MARKET",
        }.get((row.get("timeOfTheDay") or "").strip().lower(), "UNKNOWN")
        fiscal = (row.get("fiscalDateEnding") or "").strip()
        source_key = f"ALPHAVANTAGE:EARNINGS:{symbol}:{fiscal or report}"
        rows.append(
            SourceEventRecord(
                "ALPHA_VANTAGE",
                source_key,
                symbol,
                "EARNINGS",
                event_date,
                row.get("name") or f"{symbol} Earnings",
                event_session=session,
                event_time_status=(
                    "CONFIRMED_SESSION" if session != "UNKNOWN" else "UNKNOWN"
                ),
                event_components=("EPS",),
                raw_payload=dict(row),
            )
        )
    return rows


def _unfold_ical(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw_line.startswith((" ", "\t")) and lines:
            lines[-1] += raw_line[1:]
        else:
            lines.append(raw_line)
    return lines


def _parse_ical_datetime(value: str) -> tuple[date, time | None]:
    value = value.strip()
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M", "%Y%m%d"):
        try:
            parsed = datetime.strptime(value.rstrip("Z"), fmt)
            return parsed.date(), None if fmt == "%Y%m%d" else parsed.time()
        except ValueError:
            pass
    raise ValueError(f"Unsupported iCalendar datetime: {value}")


def _ical_events(text: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in _unfold_ical(text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        raw_key, value = line.split(":", 1)
        key = raw_key.split(";", 1)[0].upper()
        current[key] = value.replace("\\,", ",").replace("\\n", " ").strip()
    return events


def _normalize_bls_release(summary: str) -> tuple[str, tuple[str, ...]] | None:
    normalized = summary.lower()
    if "employment situation" in normalized:
        return (
            "EMPLOYMENT_SITUATION",
            ("NONFARM_PAYROLLS", "UNEMPLOYMENT_RATE", "AVERAGE_HOURLY_EARNINGS"),
        )
    if "consumer price index" in normalized:
        return "CPI", ()
    if "producer price index" in normalized:
        return "PPI", ()
    if "job openings and labor turnover" in normalized:
        return "JOLTS", ()
    return None


def _bls_from_ical(text: str) -> list[SourceEventRecord]:
    records: list[SourceEventRecord] = []
    for event in _ical_events(text):
        summary = event.get("SUMMARY", "").strip()
        normalized = _normalize_bls_release(summary)
        if not normalized or not event.get("DTSTART"):
            continue
        event_type, components = normalized
        event_date, event_time = _parse_ical_datetime(event["DTSTART"])
        uid = event.get("UID", "").strip()
        # UID is preferred because BLS controls it. The deterministic fallback
        # remains stable across repeated fetches of the same release period.
        period_match = re.search(r"\bfor\s+(.+)$", summary, re.I)
        period = period_match.group(1).strip() if period_match else event_date.isoformat()
        source_key = uid or f"BLS:{event_type}:{period.upper()}"
        if not source_key.startswith("BLS:"):
            source_key = f"BLS:{source_key}"
        records.append(
            SourceEventRecord(
                "BLS",
                source_key,
                "*",
                event_type,
                event_date,
                summary,
                event_time=event_time,
                event_time_status="CONFIRMED" if event_time else "UNKNOWN",
                event_components=components,
                raw_payload={
                    "calendar_format": "ICAL",
                    "uid": uid or None,
                    "summary": summary,
                    "dtstart": event.get("DTSTART"),
                    "url": BLS_ICAL_URL,
                },
            )
        )
    return list({record.source_event_key: record for record in records}.values())


def _bls_from_html(html: str, source_url: str) -> list[SourceEventRecord]:
    records: list[SourceEventRecord] = []
    wanted = {
        "Employment Situation": "EMPLOYMENT_SITUATION",
        "Consumer Price Index": "CPI",
        "Producer Price Index": "PPI",
        "Job Openings and Labor Turnover Survey": "JOLTS",
    }
    for row in ROW_RE.findall(html):
        cells = [_text(cell) for cell in CELL_RE.findall(row)]
        if len(cells) < 3:
            continue
        joined = " ".join(cells)
        release = next(
            (name for name in wanted if name.lower() in joined.lower()),
            None,
        )
        if not release:
            continue
        date_match = re.search(
            r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+"
            r"([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
            joined,
        )
        if not date_match:
            continue
        event_date = datetime.strptime(date_match.group(1), "%B %d, %Y").date()
        event_time = next(
            (parsed for cell in cells if (parsed := _parse_clock(cell)) is not None),
            None,
        )
        release_text = cells[-1]
        period = re.sub(r".*?\bfor\s+", "", release_text, flags=re.I)
        event_type = wanted[release]
        components = {
            "EMPLOYMENT_SITUATION": (
                "NONFARM_PAYROLLS",
                "UNEMPLOYMENT_RATE",
                "AVERAGE_HOURLY_EARNINGS",
            )
        }.get(event_type, ())
        source_key = f"BLS:{event_type}:{(period or event_date.isoformat()).upper()}"
        records.append(
            SourceEventRecord(
                "BLS",
                source_key,
                "*",
                event_type,
                event_date,
                release_text,
                event_time=event_time,
                event_time_status="CONFIRMED" if event_time else "UNKNOWN",
                event_components=components,
                raw_payload={
                    "calendar_format": "HTML",
                    "cells": cells,
                    "url": source_url,
                },
            )
        )
    return list({record.source_event_key: record for record in records}.values())


def bls_calendar(policy: EventSyncPolicy) -> list[SourceEventRecord]:
    errors: list[str] = []
    try:
        response = _http_get(BLS_ICAL_URL, policy, calendar=True)
        records = _bls_from_ical(response.text)
        if records:
            return records
        errors.append("official iCalendar feed returned no governed releases")
    except requests.RequestException as exc:
        errors.append(f"official iCalendar feed failed: {exc}")

    # System curl frequently succeeds on macOS where BLS rejects Python TLS/client fingerprints.
    for url, calendar in ((BLS_ICAL_URL, True), (BLS_CURRENT_YEAR_URL, False)):
        try:
            text = _curl_get_text(url, policy, calendar=calendar)
            records = _bls_from_ical(text) if calendar else _bls_from_html(text, url)
            if records:
                return records
            errors.append(f"curl fallback returned no governed releases: {url}")
        except Exception as exc:
            errors.append(f"curl fallback failed for {url}: {exc}")

    # Governed offline fallback. This file is a snapshot transcribed from the official
    # BLS 2026 release schedule. It prevents a BLS network block from leaving the
    # valuation registry empty, but it is deliberately marked DEGRADED_CACHE and is
    # never treated as authoritative for supersession/reconciliation.
    project_root = Path(__file__).resolve().parents[4]
    cache_path = project_root / "data" / "reference" / "m69_bls_release_calendar_2026.csv"
    cached_records: list[SourceEventRecord] = []
    if cache_path.exists():
        with cache_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                event_type = (row.get("event_type") or "").strip().upper()
                release_name = (row.get("release_name") or "").strip()
                event_date_text = (row.get("event_date") or "").strip()
                if not event_type or not release_name or not event_date_text:
                    continue
                event_date = date.fromisoformat(event_date_text)
                event_time = time.fromisoformat(row["event_time"]) if row.get("event_time") else None
                reference_period = (row.get("reference_period") or event_date_text).strip()
                components = {
                    "EMPLOYMENT_SITUATION": (
                        "NONFARM_PAYROLLS", "UNEMPLOYMENT_RATE", "AVERAGE_HOURLY_EARNINGS"
                    )
                }.get(event_type, ())
                cached_records.append(SourceEventRecord(
                    "BLS",
                    f"BLS:{event_type}:{reference_period.upper()}",
                    "*",
                    event_type,
                    event_date,
                    release_name,
                    event_time=event_time,
                    event_timezone=row.get("event_timezone") or "America/New_York",
                    event_time_status="CONFIRMED",
                    event_components=components,
                    source_updated_at=row.get("official_last_modified") or None,
                    raw_payload={
                        "calendar_format": "BUNDLED_OFFICIAL_SNAPSHOT",
                        "reference_period": reference_period,
                        "official_source_url": row.get("official_source_url"),
                        "official_last_modified": row.get("official_last_modified"),
                        "network_errors": errors,
                    },
                ))
    if cached_records:
        SOURCE_FETCH_METADATA["BLS"] = {
            "status": "DEGRADED_CACHE",
            "error": "BLS network access blocked; using bundled official schedule snapshot; " + "; ".join(errors),
            "fetch_mode": "BUNDLED_OFFICIAL_SNAPSHOT",
        }
        return cached_records
    raise RuntimeError("BLS calendar unavailable; " + "; ".join(errors))


def bea_calendar(policy: EventSyncPolicy) -> list[SourceEventRecord]:
    html = _http_get("https://www.bea.gov/news/schedule/full", policy).text
    records: list[SourceEventRecord] = []
    for row in ROW_RE.findall(html):
        cells = [_text(cell) for cell in CELL_RE.findall(row)]
        joined = " ".join(cells)
        if not cells or not ("GDP" in joined or "Personal Income and Outlays" in joined):
            continue
        match = re.search(r"([A-Z][a-z]+\s+\d{1,2})(?:,\s*(\d{4}))?", joined)
        if not match:
            continue
        year = int(match.group(2) or date.today().year)
        event_date = datetime.strptime(f"{match.group(1)} {year}", "%B %d %Y").date()
        event_time = next(
            (parsed for cell in cells if (parsed := _parse_clock(cell)) is not None),
            None,
        )
        if "Personal Income and Outlays" in joined:
            event_type = "PERSONAL_INCOME_AND_OUTLAYS"
            components = ("PCE", "CORE_PCE", "PERSONAL_INCOME", "PERSONAL_SPENDING")
        else:
            event_type = "GDP"
            components = ("GDP",)
        source_key = (
            f"BEA:{event_type}:{event_date.isoformat()}:"
            f'{re.sub(r"[^A-Z0-9]+", "-", joined.upper())[:80]}'
        )
        records.append(
            SourceEventRecord(
                "BEA",
                source_key,
                "*",
                event_type,
                event_date,
                joined,
                event_time=event_time,
                event_time_status="CONFIRMED" if event_time else "UNKNOWN",
                event_components=components,
                raw_payload={"cells": cells, "url": "https://www.bea.gov/news/schedule/full"},
            )
        )
    return records


def federal_reserve_fomc(policy: EventSyncPolicy) -> list[SourceEventRecord]:
    url = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
    html = _http_get(url, policy).text
    text = _text(html)
    records: list[SourceEventRecord] = []
    for year in (date.today().year, date.today().year + 1):
        marker = f"{year} FOMC Meetings"
        start_index = text.find(marker)
        if start_index < 0:
            continue
        segment = text[start_index + len(marker):]
        # The Fed page is not ordered monotonically by year (current, prior years, future).
        # Stop at the next year heading of any year so dates from minutes and other sections
        # cannot be misclassified as meetings for the requested year.
        next_heading = re.search(r"\b20\d{2} FOMC Meetings\b", segment)
        if next_heading:
            segment = segment[:next_heading.start()]
        for month, start_day, end_day in re.findall(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
            r"(\d{1,2})(?:-(\d{1,2}))?\*?",
            segment,
        ):
            start_date = date(year, datetime.strptime(month, "%B").month, int(start_day))
            end_date = date(year, start_date.month, int(end_day or start_day))
            source_key = f"FEDERAL_RESERVE:FOMC_RATE_DECISION:{end_date.isoformat()}"
            records.append(
                SourceEventRecord(
                    "FEDERAL_RESERVE",
                    source_key,
                    "*",
                    "FOMC",
                    end_date,
                    "FOMC Rate Decision",
                    event_time=time(14, 0),
                    event_time_status="GOVERNED_STANDARD_TIME",
                    event_components=("RATE_DECISION", "POLICY_STATEMENT", "PRESS_CONFERENCE"),
                    meeting_start_date=start_date,
                    meeting_end_date=end_date,
                    raw_payload={"url": url},
                )
            )
    return list({record.source_event_key: record for record in records}.values())
