from __future__ import annotations
import argparse, hashlib, json, re, subprocess
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
import requests
from sqlalchemy import text
from trading_ai.database.session import SessionLocal

UA = 'TradingPlatform-M69.6/4.0 official-event-raw-source-deterministic'
MONTHS = 'January|February|March|April|May|June|July|August|September|October|November|December'
MONTH_ALIASES = {
    'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
    'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12,
    'Jan/Feb': 2, 'Apr/May': 5, 'Oct/Nov': 11,
}


def get(url: str, timeout: int = 40) -> str | None:
    try:
        r = requests.get(url, timeout=timeout, headers={'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,*/*'})
        r.raise_for_status()
        return r.text
    except Exception:
        p = subprocess.run(['curl', '-fsSL', '--max-time', str(timeout), '-A', UA, url], capture_output=True, text=True)
        return p.stdout if p.returncode == 0 else None


def clean(value: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', value)).strip()


def stable(src: str, typ: str, period: str) -> str:
    return f'{src}:{typ}:{period.upper()}'


def upsert(session, rec: dict) -> str:
    existing = session.execute(text(
        "SELECT event_id,event_date,event_time,release_name,status FROM institutional_option_valuation_events "
        "WHERE calendar_source=:c AND source_event_key=:k"
    ), rec).mappings().first()
    target_status = 'COMPLETED' if rec['event_date'] < date.today().isoformat() else 'ACTIVE'
    if existing:
        changed = any(str(existing.get(k) or '') != str(rec.get(k) or '') for k in ('event_date', 'event_time', 'release_name'))
        sql = "UPDATE institutional_option_valuation_events SET status=:target_status,last_seen_at=:now,date_status='CONFIRMED'"
        if changed:
            sql += ",event_date=:event_date,event_time=:event_time,release_name=:release_name,revision_number=COALESCE(revision_number,1)+1,source_updated_at=:now"
        sql += " WHERE calendar_source=:c AND source_event_key=:k"
        session.execute(text(sql), {**rec, 'target_status': target_status})
        return 'updated' if changed or existing['status'] != target_status else 'unchanged'
    rec['event_id'] = 'm696-macro-' + hashlib.sha256((rec['c'] + rec['k']).encode()).hexdigest()[:24]
    session.execute(text("""INSERT INTO institutional_option_valuation_events(
        event_id,symbol,event_type,event_date,status,confidence,source,payload_json,source_event_key,
        release_name,event_time,event_timezone,event_time_status,calendar_source,date_status,
        event_components_json,evidence_json,source_updated_at,first_seen_at,last_seen_at,revision_number,
        calculation_method)
        VALUES(:event_id,'*',:typ,:event_date,:target_status,95,:c,CAST(:payload AS jsonb),:k,
        :release_name,:event_time,'America/New_York','CONFIRMED',:c,'CONFIRMED',CAST(:components AS jsonb),
        CAST(:payload AS jsonb),:now,:now,:now,1,'OFFICIAL_MACRO_HISTORY_V4')"""), {**rec, 'target_status': target_status})
    return 'created'


class _LineHTMLParser(HTMLParser):
    """Convert HTML into semantic lines while preserving heading boundaries."""
    BLOCKS = {'h1','h2','h3','h4','h5','h6','div','p','li','tr','td','th','br','section','article'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._buf: list[str] = []
        self._heading: str | None = None
        self.headings: list[tuple[str, str, int]] = []
    def _flush(self):
        value = re.sub(r'\s+', ' ', ''.join(self._buf)).strip()
        if value:
            self.lines.append(value)
        self._buf = []
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.BLOCKS:
            self._flush()
        if re.fullmatch(r'h[1-6]', tag):
            self._heading = tag
    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.BLOCKS:
            self._flush()
        if self._heading == tag:
            if self.lines:
                self.headings.append((tag, self.lines[-1], len(self.lines)-1))
            self._heading = None
    def handle_data(self, data):
        self._buf.append(data)
    def finish(self):
        self._flush()
        return self.lines, self.headings


def _html_lines(html: str):
    parser = _LineHTMLParser(); parser.feed(html); return parser.finish()


def _fomc_row(meeting_date: date, *, unscheduled: bool = False, future: bool = False,
              evidence: str = 'OFFICIAL_FOMC_MEETING') -> tuple:
    components = ['RATE_DECISION', 'SCHEDULED_MEETING' if future else 'POLICY_STATEMENT']
    if unscheduled:
        components.append('UNSCHEDULED_MEETING')
    components.append(evidence)
    return ('FEDERAL_RESERVE', 'FOMC', meeting_date.isoformat(), meeting_date,
            'FOMC Rate Decision', '14:00:00', components)


def _parse_historical_fomc_year(year: int, html: str) -> list[tuple]:
    """Parse actual meetings from official 2016-2020 historical pages."""
    _, headings = _html_lines(html)
    out = []
    pattern = re.compile(
        rf'^({MONTHS})\s+(\d{{1,2}})(?:\s*[-–—]\s*(\d{{1,2}}))?'
        rf'(?:\s*\((unscheduled)\))?\s+Meeting\s*[-–—]\s*{year}$', re.I)
    for _tag, heading, _idx in headings:
        lowered = heading.lower()
        if 'cancelled' in lowered or 'notation vote' in lowered:
            continue
        m = pattern.match(heading)
        if not m:
            continue
        month, first_day, final_day, unscheduled = m.groups()
        try:
            meeting_date = date(year, MONTH_ALIASES[month.title()], int(final_day or first_day))
        except (KeyError, ValueError):
            continue
        if meeting_date <= date.today():
            out.append(_fomc_row(meeting_date, unscheduled=bool(unscheduled), evidence='HISTORICAL_MEETING_HEADING'))
    return out


def _parse_calendar_year_sections(html: str) -> dict[int, list[str]]:
    lines, headings = _html_lines(html)
    year_heads = []
    for tag, heading, idx in headings:
        m = re.fullmatch(r'(20\d{2})\s+FOMC\s+Meetings', heading, re.I)
        if m:
            year_heads.append((int(m.group(1)), idx))
    sections: dict[int, list[str]] = {}
    for pos, (year, start) in enumerate(year_heads):
        end = year_heads[pos+1][1] if pos+1 < len(year_heads) else len(lines)
        sections[year] = lines[start+1:end]
    return sections


def _date_from_month_and_range(year: int, month_label: str, range_text: str) -> date | None:
    m = re.fullmatch(r'(\d{1,2})(?:\s*[-–—]\s*(\d{1,2}))?\*?', range_text.strip())
    if not m or month_label not in MONTH_ALIASES:
        return None
    final_day = int(m.group(2) or m.group(1))
    try:
        return date(year, MONTH_ALIASES[month_label], final_day)
    except ValueError:
        return None


def _parse_consolidated_fomc_calendar(start_year: int, html: str) -> list[tuple]:
    """Parse 2021+ completed and future meetings from one official calendar page.

    A month line followed by a date-range line defines a meeting. The content until the
    next month line determines whether an official Statement exists. Notation votes are
    excluded. Past meetings require a Statement; future meetings do not.
    """
    today = date.today(); out = []
    sections = _parse_calendar_year_sections(html)
    month_labels = set(MONTH_ALIASES)
    for year, lines in sections.items():
        if year < max(2021, start_year):
            continue
        i = 0
        while i < len(lines):
            month_label = lines[i].strip()
            if month_label not in month_labels:
                i += 1; continue
            j = i + 1
            while j < len(lines) and not re.fullmatch(r'\d{1,2}(?:\s*[-–—]\s*\d{1,2})?\*?', lines[j].strip()):
                if lines[j].strip() in month_labels:
                    break
                j += 1
            if j >= len(lines) or lines[j].strip() in month_labels:
                i += 1; continue
            meeting_date = _date_from_month_and_range(year, month_label, lines[j])
            k = j + 1
            while k < len(lines) and lines[k].strip() not in month_labels:
                k += 1
            block = ' '.join(lines[j+1:k]).lower()
            if 'notation vote' not in block and meeting_date:
                has_statement = bool(re.search(r'\bstatement\s*:', block))
                if meeting_date <= today and has_statement:
                    out.append(_fomc_row(meeting_date, evidence='CONSOLIDATED_CALENDAR_STATEMENT'))
                elif meeting_date > today:
                    out.append(_fomc_row(meeting_date, future=True, evidence='CONSOLIDATED_FORWARD_CALENDAR'))
            i = max(k, i + 1)
    return out


def fed(start_year: int):
    today = date.today(); completed = []
    for year in range(start_year, min(2020, today.year) + 1):
        html = get(f'https://www.federalreserve.gov/monetarypolicy/fomchistorical{year}.htm') or ''
        completed.extend(_parse_historical_fomc_year(year, html))
    calendar_html = get('https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm') or ''
    completed.extend(_parse_consolidated_fomc_calendar(start_year, calendar_html))
    return list({row[2]: row for row in completed}.values())


def bls(start_year, cache_dir=None):
    names = {'Consumer Price Index': 'CPI', 'Producer Price Index': 'PPI',
             'Employment Situation': 'EMPLOYMENT_SITUATION', 'Job Openings and Labor Turnover': 'JOLTS'}
    out = []
    for year in range(start_year, date.today().year + 1):
        html = None
        if cache_dir:
            path = Path(cache_dir) / f'bls_{year}.html'
            if path.exists(): html = path.read_text(errors='ignore')
        html = html or get(f'https://www.bls.gov/schedule/{year}/home.htm')
        if not html: continue
        for row in re.findall(r'(?is)<tr[^>]*>(.*?)</tr>', html):
            row_text = clean(row)
            typ = next((value for key, value in names.items() if key.lower() in row_text.lower()), None)
            dm = re.search(rf'({MONTHS})\s+(\d{{1,2}}),\s*(\d{{4}})', row_text)
            if not typ or not dm: continue
            dt = datetime.strptime(' '.join(dm.groups()), '%B %d %Y').date()
            if dt <= date.today(): out.append(('BLS', typ, dt.isoformat(), dt, row_text[:180], '08:30:00', []))
    return out


def bea(start_year):
    links, out = set(), []
    for page in range(0, 80):
        html = get('https://www.bea.gov/news/archive?field_related_product_target_id=All&page=' + str(page)) or ''
        found = {urljoin('https://www.bea.gov', link) for link in re.findall(r'href=["\']([^"\']+)["\']', html, re.I)
                 if re.search(r'/news/20\d{2}/(?:gross-domestic-product|personal-income-and-outlays)', link, re.I)}
        new = found - links; links |= found
        if page > 2 and not new: break
    for url in sorted(links):
        year_match = re.search(r'/news/(20\d{2})/', url)
        if not year_match or int(year_match.group(1)) < start_year: continue
        html = get(url) or ''; text_body = clean(html)
        typ = 'GDP' if '/gross-domestic-product' in url else 'PERSONAL_INCOME_AND_OUTLAYS'
        dm = re.search(rf'(?:RELEASE AT[^,]*,\s*)?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?,?\s*({MONTHS})\s+(\d{{1,2}}),\s*(20\d{{2}})', text_body, re.I)
        if not dm: continue
        dt = datetime.strptime(' '.join(dm.groups()), '%B %d %Y').date()
        if dt > date.today(): continue
        title_match = re.search(r'(?is)<h1[^>]*>(.*?)</h1>', html)
        name = clean(title_match.group(1)) if title_match else text_body[:180]
        components = ['PCE','CORE_PCE','PERSONAL_INCOME','PERSONAL_SPENDING'] if typ.startswith('PERSONAL') else ['GDP']
        out.append(('BEA', typ, url, dt, name, '08:30:00', components))
    return out


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--start-year', type=int, default=2016); parser.add_argument('--bls-cache-dir'); args = parser.parse_args()
    counts = {'created':0,'updated':0,'unchanged':0}; sources = {}
    with SessionLocal() as session:
        for source_name, records in [('FEDERAL_RESERVE', fed(args.start_year)), ('BLS', bls(args.start_year,args.bls_cache_dir)), ('BEA', bea(args.start_year))]:
            n = 0
            for source, typ, period, dt, name, tm, components in records:
                rec={'c':source,'k':stable(source,typ,period),'typ':typ,'event_date':dt.isoformat(),'event_time':tm,'release_name':name,'components':json.dumps(components),'payload':json.dumps({'official_source':source,'period':period,'parser_version':'V4_RAW_SOURCE_DETERMINISTIC'}),'now':datetime.now(timezone.utc)}
                counts[upsert(session,rec)] += 1; n += 1
            sources[source_name]=n
        session.commit()
    print(json.dumps({'status':'READY' if all(sources.values()) else 'DEGRADED','start_year':args.start_year,'sources':sources,**counts},indent=2,default=str))

if __name__=='__main__': main()
