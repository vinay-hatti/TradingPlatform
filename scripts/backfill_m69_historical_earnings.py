from __future__ import annotations

import argparse, csv, hashlib, json, os, time, uuid
from datetime import date, datetime, timezone
from pathlib import Path
import requests
from sqlalchemy import text
from trading_ai.database.session import SessionLocal


def load_symbols(path: str) -> list[str]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader=csv.DictReader(handle)
        if not reader.fieldnames:
            return []
        key=next((x for x in reader.fieldnames if x.lower() in {"symbol","ticker"}),reader.fieldnames[0])
        return sorted({str(row.get(key) or "").strip().upper() for row in reader if str(row.get(key) or "").strip()})


def stable_key(symbol: str, reported_date: str, fiscal_date: str) -> str:
    return f"ALPHA_VANTAGE:EARNINGS_HISTORY:{symbol}:{reported_date}:{fiscal_date or 'UNKNOWN'}"


def canonical_hash(payload: dict) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


p=argparse.ArgumentParser(description="One-time resumable Alpha Vantage historical earnings-event backfill")
p.add_argument("--universe-file",default="data/universe/us_listed_equities_etfs.csv")
p.add_argument("--start-date",default="2016-01-01")
p.add_argument("--end-date",default=date.today().isoformat())
p.add_argument("--request-interval",type=float,default=12.5)
p.add_argument("--max-symbols",type=int)
p.add_argument("--resume-file",default="reports/m69_event_intelligence/earnings_backfill_progress.json")
p.add_argument("--timeout-seconds",type=float,default=30)
a=p.parse_args()
api_key=os.getenv("ALPHAVANTAGE_API_KEY")
if not api_key:
    raise SystemExit("ALPHAVANTAGE_API_KEY is required")
start=date.fromisoformat(a.start_date);end=date.fromisoformat(a.end_date)
symbols=load_symbols(a.universe_file)
progress_path=Path(a.resume_file);progress_path.parent.mkdir(parents=True,exist_ok=True)
progress=json.loads(progress_path.read_text()) if progress_path.exists() else {"completed_symbols":[]}
completed=set(progress.get("completed_symbols",[]))
pending=[s for s in symbols if s not in completed]
if a.max_symbols: pending=pending[:a.max_symbols]
created=updated=unchanged=failed=events_seen=0
for index,symbol in enumerate(pending,1):
    try:
        response=requests.get("https://www.alphavantage.co/query",params={"function":"EARNINGS","symbol":symbol,"apikey":api_key},timeout=a.timeout_seconds,headers={"User-Agent":"TradingPlatform-M69.6/1.0"})
        response.raise_for_status();payload=response.json()
        if payload.get("Note") or payload.get("Information"):
            raise RuntimeError(payload.get("Note") or payload.get("Information"))
        rows=payload.get("quarterlyEarnings") or []
        now=datetime.now(timezone.utc).isoformat()
        with SessionLocal() as session:
            for row in rows:
                reported=str(row.get("reportedDate") or "")[:10]
                fiscal=str(row.get("fiscalDateEnding") or "")[:10]
                if not reported:
                    continue
                d=date.fromisoformat(reported)
                if d<start or d>end:
                    continue
                events_seen+=1
                key=stable_key(symbol,reported,fiscal)
                evidence={"provider_payload":row,"backfill_method":"ALPHA_VANTAGE_EARNINGS_ENDPOINT","retrieved_at":now}
                ch=canonical_hash({"symbol":symbol,"event_date":reported,"fiscal_date":fiscal,"payload":row})
                existing=session.execute(text("SELECT event_id,content_hash FROM institutional_option_valuation_events WHERE calendar_source='ALPHA_VANTAGE' AND source_event_key=:key"),{"key":key}).mappings().one_or_none()
                if existing and existing["content_hash"]==ch:
                    unchanged+=1;continue
                values={"id":existing["event_id"] if existing else f"m696-hist-{uuid.uuid4().hex}","symbol":symbol,"event_date":reported,"key":key,"release":f"{symbol} Earnings","hash":ch,"now":now,"evidence":json.dumps(evidence,default=str)}
                if existing:
                    session.execute(text("""UPDATE institutional_option_valuation_events SET event_date=:event_date,status='COMPLETED',release_name=:release,date_status='CONFIRMED',content_hash=:hash,last_seen_at=:now,source_updated_at=:now,revision_number=COALESCE(revision_number,0)+1,evidence_json=CAST(:evidence AS jsonb) WHERE event_id=:id"""),values);updated+=1
                else:
                    session.execute(text("""INSERT INTO institutional_option_valuation_events(event_id,symbol,event_type,event_date,status,expected_move_pct,historical_move_pct,confidence,source,payload_json,source_event_key,release_name,event_session,event_time_status,calendar_source,date_status,event_components_json,evidence_json,source_updated_at,first_seen_at,last_seen_at,revision_number,content_hash,record_origin) VALUES(:id,:symbol,'EARNINGS',:event_date,'COMPLETED',NULL,NULL,0,'ALPHA_VANTAGE',CAST('{}' AS jsonb),:key,:release,'UNKNOWN','UNKNOWN','ALPHA_VANTAGE','CONFIRMED',CAST('[\"EARNINGS\"]' AS jsonb),CAST(:evidence AS jsonb),:now,:now,:now,1,:hash,'AUTOMATED_HISTORICAL_BACKFILL')"""),values);created+=1
            session.commit()
        completed.add(symbol)
        progress={"completed_symbols":sorted(completed),"last_symbol":symbol,"updated_at":datetime.now(timezone.utc).isoformat(),"created":created,"updated":updated,"unchanged":unchanged,"failed":failed}
        progress_path.write_text(json.dumps(progress,indent=2,sort_keys=True))
        print(f"[{index}/{len(pending)}] {symbol}: events={len(rows)} created={created} updated={updated} unchanged={unchanged}")
    except Exception as exc:
        failed+=1;print(f"[{index}/{len(pending)}] {symbol}: FAILED {type(exc).__name__}: {exc}")
    if index<len(pending): time.sleep(max(0,a.request_interval))
print(json.dumps({"status":"READY" if failed==0 else "DEGRADED","symbols_requested":len(pending),"symbols_completed":len(completed),"events_seen":events_seen,"created":created,"updated":updated,"unchanged":unchanged,"failed":failed,"resume_file":str(progress_path)},indent=2,sort_keys=True))
