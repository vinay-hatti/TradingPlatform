#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,hashlib
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import text
from trading_ai.database.session import SessionLocal
from intraday_market_session import market_session_info

ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/"reports/market_ingestion/intraday_active_universe_shadow"
HISTORY=DIR/"history.jsonl"; LATEST=DIR/"latest.json"
VERSION="INTRADAY-ACTIVE-UNIVERSE-SHADOW-1.3.2"

# Governed intraday market-context ETF core. All other ETFs remain in the
# canonical universe and may qualify dynamically; all remain covered by EOD.
CORE_ETFS={
    # Broad market / breadth
    "SPY","QQQ","IWM","DIA","RSP",
    # 11 GICS sector proxies
    "XLB","XLC","XLE","XLF","XLI","XLK","XLP","XLRE","XLU","XLV","XLY",
    # Rates / credit
    "TLT","IEF","HYG","LQD",
    # Cross-asset
    "GLD","USO",
    # Industry bellwethers
    "SMH","XBI","KRE","XHB",
}

def load(p):
    try:return json.loads(p.read_text())
    except Exception:return {}

def universe():
    out={}
    for p in (ROOT/"data/universe/us_listed_equities_etfs.csv",ROOT/"data/universe/us_market_indices.csv"):
        if p.exists():
            for r in csv.DictReader(p.open()):
                s=str(r.get("symbol") or r.get("ticker") or "").upper().strip()
                if s:out[s]=str(r.get("asset_class") or r.get("asset_type") or "").upper()
    return out

def latest_candidates(s):
    run=s.execute(text("SELECT scanner_run_id FROM stock_scanner_publications WHERE publication_name='current_stock_intelligence' AND status IN ('READY','DEGRADED') ORDER BY snapshot_timestamp DESC LIMIT 1")).scalar()
    if not run:return None,[]
    rows=[dict(x) for x in s.execute(text("SELECT symbol,score,payload_json FROM stock_scanner_candidates WHERE scanner_run_id=:r"),{"r":run}).mappings()]
    return str(run),rows

def table_symbols(s,table,terminal=()):
    try:
        cols=set(s.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=:t"),{"t":table}).scalars())
        if "symbol" not in cols:return set()
        st=next((x for x in ("status","state","lifecycle_state","position_status","order_status") if x in cols),None)
        if st and terminal:
            vals=",".join("'"+x+"'" for x in terminal)
            q=text('SELECT DISTINCT symbol FROM "'+table+'" WHERE symbol IS NOT NULL AND UPPER(COALESCE(CAST("'+st+'" AS text),\'\')) NOT IN ('+vals+')')
        else:q=text('SELECT DISTINCT symbol FROM "'+table+'" WHERE symbol IS NOT NULL')
        return {str(x).upper() for x in s.execute(q).scalars() if x}
    except Exception:
        s.rollback();return set()

def matching_tables(s,pattern):
    return list(s.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE :p"),{"p":pattern}).scalars())

def normalize_symbol(value):
    s=str(value or "").strip().upper()
    aliases={"BF-B":"BF.B","BRK-B":"BRK.B","I:SPX":"SPX","I:NDX":"NDX","I:RTY":"RUT","RTY":"RUT"}
    return aliases.get(s,s)

def authoritative_open_positions(s):
    out=set()
    try:
        # Broker current-position truth: active, non-zero broker positions only.
        for x in s.execute(text("""
          SELECT DISTINCT symbol
          FROM broker_current_positions
          WHERE active IS TRUE
            AND COALESCE(signed_quantity,0) <> 0
            AND closed_at IS NULL
        """)).scalars():
            if x: out.add(normalize_symbol(x))
    except Exception:
        s.rollback()
    try:
        # Portfolio registry is a second authoritative safety source.
        for x in s.execute(text("""
          SELECT DISTINCT symbol
          FROM portfolio_positions
          WHERE COALESCE(quantity,0) <> 0
            AND UPPER(COALESCE(status,'')) NOT IN
              ('CLOSED','EXITED','CANCELLED','CANCELED','REJECTED','EXPIRED','SUPERSEDED','FLAT')
        """)).scalars():
            if x: out.add(normalize_symbol(x))
    except Exception:
        s.rollback()
    return out

def authoritative_working_orders(s):
    out=set()
    try:
        for x in s.execute(text("""
          SELECT DISTINCT symbol
          FROM broker_orders
          WHERE symbol IS NOT NULL
            AND COALESCE(remaining_quantity,0) > 0
            AND UPPER(COALESCE(status,'')) NOT IN
              ('FILLED','CLOSED','CANCELLED','CANCELED','REJECTED','EXPIRED','SUPERSEDED')
        """)).scalars():
            if x: out.add(normalize_symbol(x))
    except Exception:
        s.rollback()
    try:
        for x in s.execute(text("""
          SELECT DISTINCT symbol
          FROM execution_intents
          WHERE symbol IS NOT NULL
            AND terminal_at IS NULL
            AND UPPER(COALESCE(state,'')) NOT IN
              ('FILLED','CLOSED','CANCELLED','CANCELED','REJECTED','EXPIRED','SUPERSEDED')
        """)).scalars():
            if x: out.add(normalize_symbol(x))
    except Exception:
        s.rollback()
    return out

def payload_reasons(p):
    if not isinstance(p,dict): return set()
    out=set()
    volume=p.get("institutional_volume") or {}
    breakout=p.get("breakout") or {}
    event=p.get("event_intelligence") or p.get("event") or {}
    opex=p.get("opex_intelligence") or p.get("opex") or {}
    mispricing=p.get("option_mispricing") or p.get("mispricing") or {}

    volume_signal=str(volume.get("signal") or "").upper()
    volume_regime=str(volume.get("regime") or "").upper()
    if volume_signal in {
        "SELLING_ABSORPTION","BUYING_ABSORPTION","BREAKOUT_EXPANSION",
        "BREAKDOWN_EXPANSION","ACCUMULATION_CONFIRMED","DISTRIBUTION_CONFIRMED"
    } or volume_regime=="CLIMACTIC":
        out.add("INSTITUTIONAL_VOLUME_ANOMALY")

    breakout_state=str(breakout.get("state") or "").upper()
    if breakout_state in {
        "BREAKOUT_WATCH","BREAKOUT_CONFIRMED","BREAKOUT_CONTINUATION",
        "BREAKDOWN_WATCH","BREAKDOWN_CONFIRMED","FAILED_BREAKOUT"
    }:
        out.add("STRUCTURAL_BREAKOUT_BREAKDOWN")

    event_state=str(event.get("status") or event.get("state") or event.get("classification") or "").upper()
    if event_state and event_state not in {"NONE","NEUTRAL","UNAVAILABLE","NO_EVENT","INACTIVE"}:
        out.add("EVENT_RELEVANCE")

    opex_state=str(opex.get("status") or opex.get("state") or opex.get("classification") or "").upper()
    if opex_state and opex_state not in {"NONE","NEUTRAL","UNAVAILABLE","INACTIVE"}:
        out.add("OPEX_DEALER_RELEVANCE")

    mis_state=str(mispricing.get("status") or mispricing.get("state") or mispricing.get("classification") or "").upper()
    if mis_state in {"UNDERPRICED","MISPRICED","ACTIONABLE","HIGH_CONVICTION","RELATIVE_VALUE"}:
        out.add("MISPRICING_RELEVANCE")
    return out

DIRECT_POLICY_QUALIFIER_REASONS={
    "STOCK_INTELLIGENCE_HIGH_SCORE",
    "STOCK_INTELLIGENCE_DISCOVERY_COMBINATION",
    "MULTI_DOMAIN_DISCOVERY_COMBINATION",
}

def hysteresis(market_date):
    """Return bounded, session-scoped hysteresis seeded only by direct qualification.

    A symbol can be retained for at most the next two eligible intraday observations
    after a direct frozen-Policy-1.3 qualification. Hysteresis-only membership is
    deliberately non-renewing, and prior-session membership never seeds the next
    market session.
    """
    if not HISTORY.exists():return set()
    eligible=[]
    for line in HISTORY.read_text().splitlines():
        try:
            x=json.loads(line)
        except Exception:
            continue
        if x.get("mode")!="SHADOW_INTRADAY_DECISION":
            continue
        if not x.get("market_session", True):
            continue
        if str(x.get("market_date") or "")!=str(market_date or ""):
            continue
        eligible.append(x)
    out=set()
    for x in eligible[-2:]:
        reasons=x.get("inclusion_reasons") or {}
        for sym,vals in reasons.items():
            reason_set={str(v) for v in (vals or [])}
            if reason_set & DIRECT_POLICY_QUALIFIER_REASONS:
                out.add(normalize_symbol(sym))
    return out

def performance():
    life=load(ROOT/"reports/market_ingestion/options_lifecycle_latest.json")
    latest=load(ROOT/"reports/market_ingestion/options_latest.json")
    elapsed=life.get("elapsed_seconds")
    batches=latest.get("batch_results") or []
    symbols=set()
    for row in batches:
        bid=str(row.get("batch_id") or "")
        parts=bid.split(":")
        if len(parts)>=4 and parts[0]=="polygon":
            symbols.add(normalize_symbol(parts[2]))
    # Current artifact exposes one Polygon batch per captured symbol; use this as
    # a transparent symbol-request proxy, not as an HTTP request count.
    return elapsed,len(symbols),len(batches)

def intraday():
    generated_at=datetime.now(timezone.utc).isoformat()
    session_info=market_session_info(generated_at)
    u=universe()
    with SessionLocal() as s:
        run,rows=latest_candidates(s)
        positions=authoritative_open_positions(s)
        orders=authoritative_working_orders(s)
        opp={normalize_symbol(x) for x in table_symbols(s,"institutional_option_opportunities",{"RETIRED","CLOSED","SUPERSEDED","REJECTED","EXPIRED"})}
    why=defaultdict(set)
    for sym,cls in u.items():
        if sym in CORE_ETFS:
            why[sym].add("MANDATORY_CORE_ETF_REFERENCE")
        if cls=="INDEX" or sym in {"SPX","NDX","RUT"}:
            why[sym].add("MANDATORY_INDEX_REFERENCE")
    for sym in positions:why[sym].add("OPEN_POSITION")
    for sym in orders:why[sym].add("WORKING_ORDER_OR_EXECUTION")
    # Existing opportunities are retained as evidence but are not, by existence alone,
    # sufficient to force expensive intraday capture in shadow policy 1.3.
    for r in rows:
        sym=normalize_symbol(r.get("symbol")); score=float(r.get("score") or 0)
        evidence=payload_reasons(r.get("payload_json"))
        if score>=70:
            why[sym].add("STOCK_INTELLIGENCE_HIGH_SCORE")
        elif score>=60:
            # Discovery score is only sufficient when confirmed by an independent
            # structural/volume/event/OPEX/mispricing signal.
            if evidence:
                why[sym].add("STOCK_INTELLIGENCE_DISCOVERY_COMBINATION")
                why[sym] |= evidence
        else:
            # Below 60, require two independent discovery domains before full
            # intraday options work. Safety/workflow bypasses are added separately.
            if len(evidence)>=2:
                why[sym].add("MULTI_DOMAIN_DISCOVERY_COMBINATION")
                why[sym] |= evidence
    for sym in opp:
        if sym in why and why[sym]:
            why[sym].add("EXISTING_INSTITUTIONAL_OPPORTUNITY_CONTEXT")
    for sym in hysteresis(session_info.get("market_date")):
        if sym in u:why[sym].add("ELIGIBILITY_HYSTERESIS")
    active=sorted(s for s in why if s in u and why[s]); excluded=sorted(set(u)-set(active)); ratio=len(active)/max(1,len(u))
    elapsed,captured_symbols,batches=performance()
    mandatory_index_refs={"SPX","NDX","RUT"}
    opportunity_context_excluded=sorted((opp-set(active))-mandatory_index_refs)
    return {"version":VERSION,"status":"READY","mode":"SHADOW_INTRADAY_DECISION","generated_at":generated_at,**session_info,
      "stock_scanner_run_id":run,"canonical_symbols":len(u),"proposed_active_count":len(active),"proposed_excluded_count":len(excluded),
      "proposed_active_pct":round(ratio*100,2),"mandatory_core_etf_count":len(CORE_ETFS),"mandatory_core_etfs":sorted(CORE_ETFS),"proposed_active_symbols":active,"proposed_excluded_symbols":excluded,
      "inclusion_reasons":{s:sorted(why[s]) for s in active},"reason_counts":dict(Counter(x for s in active for x in why[s])),
      "safety_counts":{"open_positions":len(positions),"working_orders":len(orders),"active_opportunities":len(opp)},
      "opportunity_context_audit":{
        "excluded_existing_opportunity_count":len(opportunity_context_excluded),
        "excluded_existing_opportunity_symbols":opportunity_context_excluded,
        "mandatory_index_references":sorted(mandatory_index_refs),
        "gate":"OBSERVE_NOT_CERTIFY",
        "note":"Opportunity existence alone is not actionability. Prospective downstream progression must be observed before promotion."
      },
      "projected":{"latest_full_captured_symbols":captured_symbols,"latest_full_batches":batches,"estimated_symbol_batches_avoided":round(float(batches)*(1-ratio)),
        "latest_full_options_elapsed_seconds":elapsed,"linear_seconds_saved_reference":None if elapsed is None else round(float(elapsed)*(1-ratio),2),
        "note":"REFERENCE_ONLY_NOT_A_PERFORMANCE_GUARANTEE"},"production_effect":False}

def eod():
    u=universe(); x=load(ROOT/"reports/market_ingestion/options_lifecycle_latest.json"); y=load(ROOT/"reports/market_ingestion/options_latest.json")
    vals=[x.get("symbols"),x.get("symbol_count"),(x.get("coverage") or {}).get("symbols"),(x.get("metadata") or {}).get("symbol_count"),y.get("symbol_count"),(y.get("coverage") or {}).get("symbols")]
    reported=next((int(v) for v in vals if isinstance(v,(int,float))),None)
    generated_at=datetime.now(timezone.utc).isoformat()
    session_info=market_session_info(generated_at)
    ready=reported is not None and reported>=len(u) and session_info["market_session"]
    status="READY" if ready else ("DIAGNOSTIC" if not session_info["market_session"] else "DEGRADED")
    return {"version":VERSION,"status":status,"mode":"SHADOW_EOD_FULL_UNIVERSE_AUTHORITY",
      "generated_at":generated_at,**session_info,
      "canonical_symbols":len(u),"reported_option_symbol_coverage":reported,
      "eod_authority_ready":ready,"research_authority_eligible":ready,
      "next_morning_recovery_required":False if not session_info["market_session"] else (not ready),
      "certification_gate":"NON_MARKET_SESSION_DIAGNOSTIC" if not session_info["market_session"] else ("PASS" if ready else "FAIL"),
      "production_effect":False}

def persist(x):
    DIR.mkdir(parents=True,exist_ok=True)
    x["policy_sha256"]=hashlib.sha256(b"INTRADAY-ACTIVE-UNIVERSE-SHADOW-1.0").hexdigest()
    LATEST.write_text(json.dumps(x,indent=2,default=str)+"\n")
    with HISTORY.open("a") as f:f.write(json.dumps(x,default=str)+"\n")
    return x

def main():
    a=argparse.ArgumentParser();a.add_argument("mode",choices=("preflight","intraday","eod"));m=a.parse_args().mode
    if m=="preflight":out={"version":VERSION,"status":"READY","mode":"PREFLIGHT","canonical_symbols":len(universe()),"production_effect":False,"current_schedule_mutation":False,"future_target":"08:30-14:30 selective; 15:20 full EOD"}
    else:out=persist(intraday() if m=="intraday" else eod())
    print(json.dumps(out,indent=2,default=str))
if __name__=="__main__":main()
