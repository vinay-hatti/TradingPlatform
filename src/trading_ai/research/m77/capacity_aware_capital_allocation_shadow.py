from __future__ import annotations

import argparse
import hashlib
import json
import os
from zoneinfo import ZoneInfo
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

VERSION="M77.40.0-FROZEN-PROSPECTIVE-CAPACITY-AWARE-CAPITAL-ALLOCATION-SHADOW-1.0"
PROTOCOL_ID="CACA-CANDIDATE-001"
PROSPECTIVE_NOT_BEFORE="2026-08-28"
BINDING_VERSION="M77.40.1-GOVERNED-PRODUCTION-CAPACITY-AUTHORITY-CPRE-LIVE-INPUT-BINDING-1.0"
DEFAULT_PORTFOLIO_ID="PAPER-PRIMARY"
DEFAULT_PORTFOLIO_PUBLICATION="current_portfolio_allocation"
MARKET_TIMEZONE="America/Chicago"

# Frozen architecture. No capacity slot count is optimized or hard-coded from Development.
CONTROL_POLICY="CPRE_TOP3"
CHALLENGER_POLICY="CAPACITY_AWARE_PROBABILITY_RANKED_FILL"
RANK_SOURCE="PROBABILITY_UP"
CONTROL_TOP_K=3
MIN_MATURED_COMPARABLE_DATES=60
MIN_MATURED_ACCEPTED_OBSERVATIONS=250
MIN_UNIQUE_SYMBOLS=100
MIN_CUMULATIVE_R_UPLIFT=5.0
MIN_RETURN_PER_SLOT_UPLIFT=0.0
MIN_POSITIVE_MONTH_FRACTION=0.55
MAX_DRAWDOWN_DETERIORATION_R=5.0
MAX_WORST_MONTH_DETERIORATION_R=3.0

class CapacityAwareShadowError(RuntimeError):
    pass

@dataclass(frozen=True)
class CapacityAwareShadowConfig:
    project_root:str
    protocol_path:str="data/capacity_aware_capital_allocation_shadow/FROZEN_PROSPECTIVE_PROTOCOL.json"
    snapshot_dir:str="data/capacity_aware_capital_allocation_shadow/snapshots"
    matured_dir:str="data/capacity_aware_capital_allocation_shadow/matured"
    summary_path:str="data/capacity_aware_capital_allocation_shadow/certification_summary.json"
    state_path:str="data/capacity_aware_capital_allocation_shadow/state.json"
    # The recorder may use a live export produced by the user's current platform.
    live_candidate_snapshot_path:str="data/capacity_aware_capital_allocation_shadow/live_candidate_snapshot.csv"
    live_capacity_state_path:str="data/capacity_aware_capital_allocation_shadow/live_capacity_state.json"
    # Outcome authority is deliberately local/shadow and must not open 2018-2026 historical outcomes for tuning.
    outcome_update_path:str="data/capacity_aware_capital_allocation_shadow/outcome_updates.csv"
    cpre_snapshot_dir:str="data/cross_sectional_capital_priority_shadow/snapshots"
    portfolio_id:str=DEFAULT_PORTFOLIO_ID
    auto_bind_live_authority:bool=False


def _resolve(root:Path,raw:str)->Path:
    p=Path(raw).expanduser()
    return p if p.is_absolute() else root/p

def _json_default(v:Any)->Any:
    if isinstance(v,(np.integer,)): return int(v)
    if isinstance(v,(np.floating,)): return None if not np.isfinite(v) else float(v)
    if isinstance(v,(pd.Timestamp,datetime)): return v.isoformat()
    if isinstance(v,Path): return str(v)
    raise TypeError(type(v).__name__)

def _atomic_json(path:Path,payload:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,sort_keys=True,default=_json_default))
    os.replace(tmp,path)

def _sha_bytes(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def _protocol_payload()->dict[str,Any]:
    payload={
        "version":VERSION,
        "protocol_id":PROTOCOL_ID,
        "prospective_not_before":PROSPECTIVE_NOT_BEFORE,
        "population":"TRADE_BUILDER_READY_LONG_AND_DRVE_PASS",
        "rank_source":RANK_SOURCE,
        "control_policy":{
            "name":CONTROL_POLICY,
            "definition":"Select at most the top 3 eligible candidates per market-date cohort by PROBABILITY_UP descending, then respect actual governed available capacity.",
            "top_k":CONTROL_TOP_K,
        },
        "challenger_policy":{
            "name":CHALLENGER_POLICY,
            "definition":"Fill actual governed available capacity in PROBABILITY_UP descending order; no fixed slot count is selected by this protocol.",
            "capacity_source":"LIVE_GOVERNED_AVAILABLE_CAPACITY_AT_SNAPSHOT_TIME",
        },
        "snapshot_policy":"FIRST_IMMUTABLE_SNAPSHOT_PER_MARKET_DATE",
        "management":"EXISTING_CERTIFIED_PRODUCTION_MANAGEMENT_SEMANTICS_UNCHANGED",
        "outcome_semantics":"SHADOW_REALIZED_OUTCOME_FROM_PROSPECTIVE_SNAPSHOT_ONLY",
        "frozen_gates":{
            "minimum_matured_comparable_dates":MIN_MATURED_COMPARABLE_DATES,
            "minimum_matured_accepted_observations":MIN_MATURED_ACCEPTED_OBSERVATIONS,
            "minimum_unique_symbols":MIN_UNIQUE_SYMBOLS,
            "minimum_cumulative_r_uplift":MIN_CUMULATIVE_R_UPLIFT,
            "minimum_return_per_slot_uplift":MIN_RETURN_PER_SLOT_UPLIFT,
            "minimum_positive_month_fraction":MIN_POSITIVE_MONTH_FRACTION,
            "maximum_drawdown_deterioration_r":MAX_DRAWDOWN_DETERIORATION_R,
            "maximum_worst_month_deterioration_r":MAX_WORST_MONTH_DETERIORATION_R,
        },
        "new_probability_up_thresholds_tested":0,
        "new_top_k_values_tested":0,
        "capacity_budgets_retuned":False,
        "management_geometry_retuned":False,
        "automatic_retraining":False,
        "production_capital_allocation_effect":False,
    }
    payload["protocol_sha256"]=_sha_bytes(json.dumps(payload,sort_keys=True,separators=(",",":")).encode())
    return payload

def freeze_protocol(cfg:CapacityAwareShadowConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    pp=_resolve(root,cfg.protocol_path)
    payload=_protocol_payload()
    if pp.exists():
        existing=json.loads(pp.read_text())
        if existing!=payload:
            raise CapacityAwareShadowError("Frozen prospective protocol already exists with different contents")
        return {"status":"ALREADY_FROZEN","protocol_path":str(pp.relative_to(root)),"protocol_id":PROTOCOL_ID}
    _atomic_json(pp,payload)
    return {"status":"FROZEN","protocol_path":str(pp.relative_to(root)),"protocol_id":PROTOCOL_ID}

def _load_protocol(root:Path,cfg:CapacityAwareShadowConfig)->dict[str,Any]:
    pp=_resolve(root,cfg.protocol_path)
    if not pp.exists():
        raise CapacityAwareShadowError("Protocol is not frozen; run --action freeze first")
    p=json.loads(pp.read_text())
    if p!=_protocol_payload():
        raise CapacityAwareShadowError("Frozen protocol contents do not match code contract")
    return p

def _parse_timestamp(raw:Any)->datetime:
    if isinstance(raw,datetime):
        dt=raw
    else:
        text=str(raw or "").strip().replace("Z","+00:00")
        if not text:
            raise CapacityAwareShadowError("Missing authority timestamp")
        try:
            dt=datetime.fromisoformat(text)
        except ValueError as exc:
            raise CapacityAwareShadowError(f"Invalid authority timestamp: {raw}") from exc
    if dt.tzinfo is None:
        dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _market_date_for_timestamp(raw:Any)->str:
    return _parse_timestamp(raw).astimezone(ZoneInfo(MARKET_TIMEZONE)).date().isoformat()

def _latest_cpre_snapshot(root:Path,cfg:CapacityAwareShadowConfig)->tuple[Path,dict[str,Any]]:
    sd=_resolve(root,cfg.cpre_snapshot_dir)
    if not sd.exists():
        raise CapacityAwareShadowError(f"CPRE prospective snapshot directory missing: {sd}")
    eligible=[]
    for path in sorted(sd.glob("*.json")):
        try:
            payload=json.loads(path.read_text())
        except Exception as exc:
            raise CapacityAwareShadowError(f"Invalid CPRE snapshot JSON: {path}") from exc
        date=str(payload.get("market_as_of_date") or path.stem)
        if date>=PROSPECTIVE_NOT_BEFORE:
            eligible.append((date,path,payload))
    if not eligible:
        raise CapacityAwareShadowError("No post-boundary immutable CPRE snapshot is available")
    _,path,payload=max(eligible,key=lambda item:item[0])
    if payload.get("protocol_id")!="CPRE-CANDIDATE-001":
        raise CapacityAwareShadowError("CPRE snapshot protocol_id is not CPRE-CANDIDATE-001")
    if payload.get("population")!="TRADE_BUILDER_READY_LONG_AND_DRVE_PASS":
        raise CapacityAwareShadowError("CPRE snapshot population is not the frozen eligible population")
    if payload.get("ranker")!="PROBABILITY_UP_DESCENDING":
        raise CapacityAwareShadowError("CPRE snapshot ranker is not PROBABILITY_UP_DESCENDING")
    if payload.get("immutable_first_snapshot_per_market_date") is not True:
        raise CapacityAwareShadowError("CPRE snapshot is not marked immutable-first-per-market-date")
    records=payload.get("records") or []
    if not records:
        raise CapacityAwareShadowError("CPRE snapshot has no ranked records")
    return path,payload

def _cpre_to_candidate_frame(payload:dict[str,Any])->pd.DataFrame:
    market_date=str(payload["market_as_of_date"])
    rows=[]
    for r in payload.get("records") or []:
        rows.append({
            "symbol":str(r["symbol"]).upper(),
            "market_as_of_date":market_date,
            "probability_up":float(r["probability_up"]),
            "trade_builder_ready":True,
            "drv_pass":True,
            "cpre_probability_rank":int(r["probability_up_rank"]),
            "cpre_selected_top3":bool(r.get("selected_top3",False)),
        })
    frame=pd.DataFrame(rows)
    if frame["symbol"].duplicated().any():
        raise CapacityAwareShadowError("Duplicate symbol in CPRE ranked cohort")
    expected=list(range(1,len(frame)+1))
    actual=sorted(frame["cpre_probability_rank"].tolist())
    if actual!=expected:
        raise CapacityAwareShadowError("CPRE probability ranks are not contiguous 1..N")
    return frame.sort_values(["cpre_probability_rank","symbol"]).reset_index(drop=True)

def _latest_ready_portfolio_allocation(
    portfolio_id:str,
    market_date:str,
)->dict[str,Any]:
    # Resolve effective market date through immutable Stock Intelligence lineage.
    try:
        from sqlalchemy import text
        from trading_ai.database.session import SessionLocal
    except Exception as exc:
        raise CapacityAwareShadowError(
            "Unable to import production portfolio-allocation authority reader"
        ) from exc

    session=SessionLocal()
    try:
        rows=session.execute(text("""
            SELECT publication_id, publication_name, portfolio_id,
                   risk_snapshot_id, optimization_snapshot_id,
                   published_at, status, payload_json
            FROM portfolio_allocation_publications
            WHERE publication_name = :publication_name
              AND portfolio_id = :portfolio_id
              AND status = 'READY'
            ORDER BY published_at DESC
            LIMIT 256
        """),{
            "publication_name":DEFAULT_PORTFOLIO_PUBLICATION,
            "portfolio_id":portfolio_id,
        }).mappings().all()

        if not rows:
            raise CapacityAwareShadowError(
                f"No READY {DEFAULT_PORTFOLIO_PUBLICATION} authority for portfolio {portfolio_id}"
            )

        observed=[]
        for raw in rows:
            row=dict(raw)
            opt_id=row.get("optimization_snapshot_id")
            if not opt_id:
                observed.append({
                    "publication_id": row.get("publication_id"),
                    "reason": "MISSING_OPTIMIZATION_SNAPSHOT_ID",
                })
                continue

            opt=session.execute(text("""
                SELECT optimization_snapshot_id, payload_json
                FROM portfolio_optimization_snapshots
                WHERE optimization_snapshot_id = :optimization_snapshot_id
                LIMIT 1
            """),{"optimization_snapshot_id":opt_id}).mappings().first()

            if opt is None:
                observed.append({
                    "publication_id": row.get("publication_id"),
                    "optimization_snapshot_id": opt_id,
                    "reason": "OPTIMIZATION_SNAPSHOT_NOT_FOUND",
                })
                continue

            opt_payload=dict(opt).get("payload_json") or {}
            if not isinstance(opt_payload,dict):
                opt_payload={}
            scanner_run_id=opt_payload.get("stock_scanner_run_id")
            if not scanner_run_id:
                authority_input=opt_payload.get("authority_input") or {}
                if isinstance(authority_input,dict):
                    scanner_run_id=authority_input.get("stock_scanner_run_id")

            if not scanner_run_id:
                observed.append({
                    "publication_id": row.get("publication_id"),
                    "optimization_snapshot_id": opt_id,
                    "reason": "STOCK_SCANNER_RUN_ID_MISSING_FROM_OPTIMIZATION_LINEAGE",
                })
                continue

            scanner=session.execute(text("""
                SELECT scanner_run_id, payload_json
                FROM stock_scanner_runs
                WHERE scanner_run_id = :scanner_run_id
                LIMIT 1
            """),{"scanner_run_id":scanner_run_id}).mappings().first()

            effective_market_date=None
            source=None

            if scanner is not None:
                scanner_payload=dict(scanner).get("payload_json") or {}
                if isinstance(scanner_payload,dict):
                    lineage=scanner_payload.get("lineage") or {}
                    if isinstance(lineage,dict):
                        value=lineage.get("market_as_of_date")
                        if value:
                            effective_market_date=str(value)
                            source="stock_scanner_runs.payload_json.lineage.market_as_of_date"

            if not effective_market_date:
                lineage_row=session.execute(text("""
                    SELECT market_as_of_date
                    FROM scanner_lineage_run
                    WHERE scanner_run_id = :scanner_run_id
                    LIMIT 1
                """),{"scanner_run_id":scanner_run_id}).mappings().first()
                if lineage_row and lineage_row.get("market_as_of_date"):
                    effective_market_date=str(lineage_row.get("market_as_of_date"))
                    source="scanner_lineage_run.market_as_of_date"

            observed.append({
                "publication_id": row.get("publication_id"),
                "optimization_snapshot_id": opt_id,
                "stock_scanner_run_id": scanner_run_id,
                "effective_market_date": effective_market_date,
                "effective_market_date_source": source,
            })

            if effective_market_date == market_date:
                row["_effective_market_date"]=effective_market_date
                row["_effective_market_date_source"]=source
                row["_stock_scanner_run_id"]=scanner_run_id
                return row

        raise CapacityAwareShadowError(
            f"No READY {DEFAULT_PORTFOLIO_PUBLICATION} authority resolves to "
            f"CPRE market date {market_date}; observed_recent_lineage={observed[:10]}"
        )
    finally:
        session.close()
def _capacity_from_publication(row:dict[str,Any],market_date:str)->dict[str,Any]:
    payload=row.get("payload_json") or {}
    if isinstance(payload,str):
        payload=json.loads(payload)
    if not isinstance(payload,dict):
        raise CapacityAwareShadowError("Portfolio allocation payload_json is not an object")
    published_at=row.get("published_at")
    publication_market_date=_market_date_for_timestamp(published_at)

    # M78.2.4: published_at is a processing/publication timestamp, not the
    # authoritative market-session date. The selector has already resolved
    # the immutable effective market date through:
    # portfolio publication -> optimization -> stock scanner -> market_as_of_date.
    effective_market_date=row.get("_effective_market_date")
    effective_market_date_source=row.get("_effective_market_date_source")

    if not effective_market_date:
        raise CapacityAwareShadowError(
            "Portfolio allocation effective market date missing after "
            "governed lineage resolution"
        )

    if str(effective_market_date) != str(market_date):
        raise CapacityAwareShadowError(
            f"Portfolio allocation effective market-date mismatch: "
            f"CPRE={market_date}, "
            f"portfolio_effective_market_date={effective_market_date}, "
            f"source={effective_market_date_source}, "
            f"publication_processing_date={publication_market_date}"
        )
    objective=payload.get("objective") or {}
    target=payload.get("target_portfolio") or {}
    proof=payload.get("optimization_proof") or {}
    selected_values=[
        v for v in (
            objective.get("selected_count"),
            target.get("selected_opportunity_count"),
            proof.get("selected_count"),
        ) if v is not None
    ]
    if not selected_values:
        raise CapacityAwareShadowError("Portfolio authority does not expose a feasible selected-count")
    selected_count=int(selected_values[0])
    if any(int(v)!=selected_count for v in selected_values):
        raise CapacityAwareShadowError(f"Portfolio selected-count authorities disagree: {selected_values}")
    risk_budgets=payload.get("risk_budgets") or {}
    portfolio_budget=risk_budgets.get("portfolio") or {}
    current=payload.get("current_portfolio") or {}
    policy=payload.get("resolved_optimizer_policy") or {}
    if selected_count<0:
        raise CapacityAwareShadowError("Portfolio feasible selected-count cannot be negative")
    # M77.40 needs an integer capacity axis for the frozen control/challenger comparison.
    # Production M64 exposes no literal slot counter; its exact optimizer exposes the
    # contemporaneous number of candidates admitted under all governed constraints.
    # We use that observed feasible count only as a shadow slot-equivalent and retain
    # the complete capital/risk provenance below. It is never written back to M64.
    return {
        "market_as_of_date":market_date,
        "total_slots":selected_count,
        "occupied_slots":0,
        "available_slots":selected_count,
        "capacity_measure":"M64_EXACT_OPTIMIZER_FEASIBLE_SELECTED_COUNT_SLOT_EQUIVALENT",
        "capacity_measure_semantics":"Shadow comparison axis only; not a production max-position or literal free-slot rule.",
        "publication_id":row.get("publication_id"),
        "publication_name":row.get("publication_name"),
        "portfolio_id":row.get("portfolio_id"),
        "risk_snapshot_id":row.get("risk_snapshot_id"),
        "optimization_snapshot_id":row.get("optimization_snapshot_id"),
        "published_at":str(published_at),
        "publication_market_date":publication_market_date,
        "optimizer_policy_version":payload.get("policy_version"),
        "max_new_positions":policy.get("max_new_positions"),
        "max_new_positions_source":policy.get("max_new_positions_source"),
        "new_capital_limit":portfolio_budget.get("new_capital_limit"),
        "new_capital_remaining":portfolio_budget.get("new_capital_remaining"),
        "net_liquidation":portfolio_budget.get("net_liquidation",current.get("net_liquidation")),
        "buying_power":portfolio_budget.get("buying_power",current.get("buying_power")),
        "capital_committed":current.get("capital_committed"),
        "portfolio_heat_pct":portfolio_budget.get("portfolio_heat_pct",current.get("portfolio_heat_pct")),
        "portfolio_heat_limit_pct":portfolio_budget.get("portfolio_heat_limit_pct"),
        "limits":risk_budgets.get("limits") or {},
        "breaches":risk_budgets.get("breaches") or [],
        "optimizer_selected_count":selected_count,
        "optimizer_rejected_count":objective.get("rejected_count"),
        "optimality_proven":proof.get("optimality_proven"),
        "production_capital_allocation_effect":False,
    }

def bind_live_inputs(cfg:CapacityAwareShadowConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    _load_protocol(root,cfg)
    cpre_path,cpre=_latest_cpre_snapshot(root,cfg)
    candidates=_cpre_to_candidate_frame(cpre)
    market_date=str(cpre["market_as_of_date"])
    row=_latest_ready_portfolio_allocation(cfg.portfolio_id,market_date)
    capacity=_capacity_from_publication(row,market_date)
    candidate_path=_resolve(root,cfg.live_candidate_snapshot_path)
    capacity_path=_resolve(root,cfg.live_capacity_state_path)
    candidate_path.parent.mkdir(parents=True,exist_ok=True)
    tmp=candidate_path.with_suffix(candidate_path.suffix+".tmp")
    candidates.to_csv(tmp,index=False)
    os.replace(tmp,candidate_path)
    capacity.update({
        "binding_version":BINDING_VERSION,
        "bound_at":datetime.now(timezone.utc).isoformat(),
        "candidate_authority_protocol_id":cpre.get("protocol_id"),
        "candidate_authority_run_id":cpre.get("stock_scanner_run_id"),
        "candidate_authority_source_model_fingerprint":cpre.get("source_model_fingerprint"),
        "candidate_authority_frozen_at":cpre.get("frozen_at"),
        "candidate_authority_snapshot_path":str(cpre_path.relative_to(root)),
        "candidate_authority_snapshot_sha256":_sha_bytes(cpre_path.read_bytes()),
        "candidate_authority_record_count":len(candidates),
        "candidate_and_capacity_scanner_run_equality_required":False,
        "production_authority_effect":False,
    })
    _atomic_json(capacity_path,capacity)
    return {
        "version":BINDING_VERSION,
        "status":"BOUND",
        "market_as_of_date":market_date,
        "candidate_snapshot_path":str(candidate_path.relative_to(root)),
        "capacity_state_path":str(capacity_path.relative_to(root)),
        "candidate_count":len(candidates),
        "candidate_authority_run_id":cpre.get("stock_scanner_run_id"),
        "capacity_publication_id":capacity.get("publication_id"),
        "capacity_published_at":capacity.get("published_at"),
        "capacity_slot_equivalent":capacity.get("available_slots"),
        "capacity_measure":capacity.get("capacity_measure"),
        "production_authority_effect":False,
    }

def _load_capacity(path:Path)->dict[str,Any]:
    if not path.exists():
        raise CapacityAwareShadowError(
            f"Live governed capacity state missing: {path}. "
            "Recorder requires a current platform export with market_as_of_date, total_slots, occupied_slots, available_slots."
        )
    c=json.loads(path.read_text())
    req=("market_as_of_date","total_slots","occupied_slots","available_slots")
    missing=[k for k in req if k not in c]
    if missing: raise CapacityAwareShadowError(f"Capacity state missing fields: {missing}")
    for k in ("total_slots","occupied_slots","available_slots"):
        c[k]=int(c[k])
    if c["available_slots"]<0 or c["occupied_slots"]<0 or c["total_slots"]<0:
        raise CapacityAwareShadowError("Capacity values must be non-negative")
    if c["occupied_slots"]+c["available_slots"]!=c["total_slots"]:
        raise CapacityAwareShadowError("Capacity state inconsistent: occupied + available != total")
    return c

def _load_candidates(path:Path)->pd.DataFrame:
    if not path.exists():
        raise CapacityAwareShadowError(
            f"Live candidate snapshot missing: {path}. "
            "Recorder requires a current point-in-time export of Trade-Builder-ready LONG candidates with DRVE PASS."
        )
    p=pd.read_csv(path)
    required=("symbol","market_as_of_date","probability_up","trade_builder_ready","drv_pass")
    missing=[c for c in required if c not in p.columns]
    if missing: raise CapacityAwareShadowError(f"Candidate snapshot missing fields: {missing}")
    p["symbol"]=p["symbol"].astype(str).str.upper()
    p["market_as_of_date"]=pd.to_datetime(p["market_as_of_date"],errors="coerce").dt.date.astype(str)
    p["probability_up"]=pd.to_numeric(p["probability_up"],errors="coerce")
    if p["probability_up"].isna().any(): raise CapacityAwareShadowError("Candidate PROBABILITY_UP contains missing values")
    def _bool(s):
        if s.dtype==bool:return s
        return s.astype(str).str.lower().isin(["true","1","yes","y","pass","ready"])
    p["trade_builder_ready"]=_bool(p["trade_builder_ready"])
    p["drv_pass"]=_bool(p["drv_pass"])
    p=p[p["trade_builder_ready"] & p["drv_pass"]].copy()
    if p.duplicated(["symbol","market_as_of_date"]).any():
        raise CapacityAwareShadowError("Duplicate eligible candidate identity in live snapshot")
    return p

def _select(p:pd.DataFrame,available_slots:int)->pd.DataFrame:
    x=p.sort_values(["probability_up","symbol"],ascending=[False,True]).copy()
    x["probability_rank"]=np.arange(1,len(x)+1)
    x["control_selected"]=(x["probability_rank"]<=CONTROL_TOP_K) & (x["probability_rank"]<=available_slots)
    x["challenger_selected"]=x["probability_rank"]<=available_slots
    return x

def record_snapshot(cfg:CapacityAwareShadowConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    protocol=_load_protocol(root,cfg)
    binding=None
    if cfg.auto_bind_live_authority:
        binding=bind_live_inputs(cfg)
    cap=_load_capacity(_resolve(root,cfg.live_capacity_state_path))
    candidates=_load_candidates(_resolve(root,cfg.live_candidate_snapshot_path))
    market_date=str(cap["market_as_of_date"])
    if market_date<PROSPECTIVE_NOT_BEFORE:
        return {
            "status":"SKIPPED_PRE_BOUNDARY",
            "market_as_of_date":market_date,
            "prospective_not_before":PROSPECTIVE_NOT_BEFORE,
            "production_authority_effect":False,
        }
    dates=set(candidates["market_as_of_date"].unique())
    if dates and dates!={market_date}:
        raise CapacityAwareShadowError(f"Candidate snapshot market date mismatch: candidate_dates={sorted(dates)}, capacity_date={market_date}")
    sd=_resolve(root,cfg.snapshot_dir);sd.mkdir(parents=True,exist_ok=True)
    out=sd/f"{market_date}.json"
    if out.exists():
        existing=json.loads(out.read_text())
        return {
            "status":"ALREADY_RECORDED_IMMUTABLE",
            "market_as_of_date":market_date,
            "snapshot_path":str(out.relative_to(root)),
            "snapshot_sha256":_sha_bytes(out.read_bytes()),
            "control_selected":len(existing.get("control_selected",[])),
            "challenger_selected":len(existing.get("challenger_selected",[])),
            "production_authority_effect":False,
        }
    selected=_select(candidates,cap["available_slots"])
    records=selected[["symbol","probability_up","probability_rank"]].to_dict("records")
    control=selected[selected["control_selected"]][["symbol","probability_up","probability_rank"]].to_dict("records")
    challenger=selected[selected["challenger_selected"]][["symbol","probability_up","probability_rank"]].to_dict("records")
    payload={
        "version":VERSION,
        "protocol_id":PROTOCOL_ID,
        "protocol_sha256":protocol["protocol_sha256"],
        "recorded_at":datetime.now(timezone.utc).isoformat(),
        "market_as_of_date":market_date,
        "capacity":{
            "total_slots":cap["total_slots"],
            "occupied_slots":cap["occupied_slots"],
            "available_slots":cap["available_slots"],
        },
        "eligible_ranked_cohort":records,
        "control_selected":control,
        "challenger_selected":challenger,
        "authority_binding":binding,
        "capacity_authority":{k:v for k,v in cap.items() if k not in ("total_slots","occupied_slots","available_slots")},
        "production_authority_effect":False,
    }
    _atomic_json(out,payload)
    return {
        "status":"RECORDED",
        "market_as_of_date":market_date,
        "snapshot_path":str(out.relative_to(root)),
        "snapshot_sha256":_sha_bytes(out.read_bytes()),
        "eligible_candidates":len(records),
        "control_selected":len(control),
        "challenger_selected":len(challenger),
        "available_slots":cap["available_slots"],
        "production_authority_effect":False,
    }

def _load_outcomes(path:Path)->pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["market_as_of_date","symbol","realized_r","matured_at"])
    o=pd.read_csv(path)
    required=("market_as_of_date","symbol","realized_r","matured_at")
    missing=[c for c in required if c not in o.columns]
    if missing: raise CapacityAwareShadowError(f"Outcome update file missing fields: {missing}")
    o["market_as_of_date"]=pd.to_datetime(o["market_as_of_date"],errors="coerce").dt.date.astype(str)
    o["symbol"]=o["symbol"].astype(str).str.upper()
    o["realized_r"]=pd.to_numeric(o["realized_r"],errors="coerce")
    o["matured_at"]=pd.to_datetime(o["matured_at"],errors="coerce")
    if o[["realized_r","matured_at"]].isna().any().any():
        raise CapacityAwareShadowError("Outcome update contains invalid realized_r or matured_at")
    if o.duplicated(["market_as_of_date","symbol"]).any():
        raise CapacityAwareShadowError("Duplicate shadow outcome identity")
    return o

def update_matured(cfg:CapacityAwareShadowConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    _load_protocol(root,cfg)
    sd=_resolve(root,cfg.snapshot_dir)
    md=_resolve(root,cfg.matured_dir);md.mkdir(parents=True,exist_ok=True)
    outcomes=_load_outcomes(_resolve(root,cfg.outcome_update_path))
    matured_new=0
    if sd.exists():
        for snap_path in sorted(sd.glob("*.json")):
            snap=json.loads(snap_path.read_text())
            date=snap["market_as_of_date"]
            out_path=md/f"{date}.json"
            if out_path.exists(): continue
            selected={}
            for policy,key in ((CONTROL_POLICY,"control_selected"),(CHALLENGER_POLICY,"challenger_selected")):
                for r in snap[key]:
                    selected[(policy,r["symbol"])]=r
            rows=[]
            complete=True
            for (policy,sym),r in selected.items():
                m=outcomes[(outcomes["market_as_of_date"]==date)&(outcomes["symbol"]==sym)]
                if m.empty:
                    complete=False
                    break
                rows.append({
                    "policy":policy,
                    "symbol":sym,
                    "probability_up":r["probability_up"],
                    "probability_rank":r["probability_rank"],
                    "realized_r":float(m.iloc[0]["realized_r"]),
                    "matured_at":m.iloc[0]["matured_at"].isoformat(),
                })
            if complete and selected:
                payload={
                    "version":VERSION,
                    "protocol_id":PROTOCOL_ID,
                    "market_as_of_date":date,
                    "capacity":snap["capacity"],
                    "rows":rows,
                    "production_authority_effect":False,
                }
                _atomic_json(out_path,payload)
                matured_new+=1
    summary=evaluate(cfg)
    summary["matured_new"]=matured_new
    return summary

def _policy_metrics(df:pd.DataFrame,policy:str)->dict[str,Any]:
    g=df[df["policy"]==policy].copy()
    if g.empty:return {"accepted_n":0}
    r=g["realized_r"].astype(float)
    gp=float(r[r>0].sum());gl=float(-r[r<0].sum())
    # Daily portfolio R is sum of accepted shadow trade outcomes by snapshot date.
    daily=g.groupby("market_as_of_date")["realized_r"].sum().sort_index()
    monthly=g.assign(month=pd.to_datetime(g["market_as_of_date"]).dt.to_period("M")).groupby("month")["realized_r"].sum()
    cumulative=daily.cumsum()
    dd=cumulative-cumulative.cummax()
    slots=g.groupby("market_as_of_date")["available_slots"].first()
    return {
        "accepted_n":int(len(g)),
        "unique_symbols":int(g["symbol"].nunique()),
        "comparable_dates":int(g["market_as_of_date"].nunique()),
        "cumulative_r":float(r.sum()),
        "mean_r":float(r.mean()),
        "profit_factor":float(gp/gl) if gl>0 else np.inf,
        "positive_month_fraction":float((monthly>0).mean()) if len(monthly) else np.nan,
        "worst_month_r":float(monthly.min()) if len(monthly) else np.nan,
        "max_cumulative_r_drawdown":float(dd.min()) if len(dd) else np.nan,
        "return_per_slot":float(daily.sum()/slots.sum()) if slots.sum()>0 else np.nan,
    }

def _collect_matured(root:Path,cfg:CapacityAwareShadowConfig)->pd.DataFrame:
    md=_resolve(root,cfg.matured_dir)
    rows=[]
    if not md.exists(): return pd.DataFrame()
    for p in sorted(md.glob("*.json")):
        x=json.loads(p.read_text())
        avail=int(x["capacity"]["available_slots"])
        for r in x["rows"]:
            rows.append({
                "market_as_of_date":x["market_as_of_date"],
                "available_slots":avail,
                **r,
            })
    return pd.DataFrame(rows)

def evaluate(cfg:CapacityAwareShadowConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    protocol=_load_protocol(root,cfg)
    df=_collect_matured(root,cfg)
    if df.empty:
        out={
            "version":VERSION,
            "protocol_id":PROTOCOL_ID,
            "status":"ACCUMULATING",
            "certification_verdict":"NOT_ENOUGH_PROSPECTIVE_EVIDENCE",
            "matured_comparable_dates":0,
            "matured_control_observations":0,
            "matured_challenger_observations":0,
            "production_authority_effect":False,
            "frozen_gates":protocol["frozen_gates"],
        }
        _atomic_json(_resolve(root,cfg.summary_path),out)
        return out

    control=_policy_metrics(df,CONTROL_POLICY)
    challenger=_policy_metrics(df,CHALLENGER_POLICY)
    common_dates=set(df[df["policy"]==CONTROL_POLICY]["market_as_of_date"]) & set(df[df["policy"]==CHALLENGER_POLICY]["market_as_of_date"])
    gates={
        "minimum_matured_comparable_dates":len(common_dates)>=MIN_MATURED_COMPARABLE_DATES,
        "minimum_matured_accepted_observations":challenger.get("accepted_n",0)>=MIN_MATURED_ACCEPTED_OBSERVATIONS,
        "minimum_unique_symbols":challenger.get("unique_symbols",0)>=MIN_UNIQUE_SYMBOLS,
        "minimum_cumulative_r_uplift":(
            challenger.get("cumulative_r",-np.inf)-control.get("cumulative_r",np.inf)
        )>=MIN_CUMULATIVE_R_UPLIFT,
        "minimum_return_per_slot_uplift":(
            challenger.get("return_per_slot",-np.inf)-control.get("return_per_slot",np.inf)
        )>=MIN_RETURN_PER_SLOT_UPLIFT,
        "minimum_positive_month_fraction":challenger.get("positive_month_fraction",-np.inf)>=MIN_POSITIVE_MONTH_FRACTION,
        "maximum_drawdown_deterioration_r":(
            challenger.get("max_cumulative_r_drawdown",-np.inf)-control.get("max_cumulative_r_drawdown",np.inf)
        )>=-MAX_DRAWDOWN_DETERIORATION_R,
        "maximum_worst_month_deterioration_r":(
            challenger.get("worst_month_r",-np.inf)-control.get("worst_month_r",np.inf)
        )>=-MAX_WORST_MONTH_DETERIORATION_R,
    }
    enough=(
        gates["minimum_matured_comparable_dates"]
        and gates["minimum_matured_accepted_observations"]
        and gates["minimum_unique_symbols"]
    )
    verdict="PASS" if enough and all(gates.values()) else ("FAIL" if enough else "NOT_ENOUGH_PROSPECTIVE_EVIDENCE")
    out={
        "version":VERSION,
        "protocol_id":PROTOCOL_ID,
        "status":"COMPLETE" if enough else "ACCUMULATING",
        "certification_verdict":verdict,
        "matured_comparable_dates":len(common_dates),
        "matured_control_observations":control.get("accepted_n",0),
        "matured_challenger_observations":challenger.get("accepted_n",0),
        "control_metrics":control,
        "challenger_metrics":challenger,
        "incremental":{
            "cumulative_r_uplift":challenger.get("cumulative_r",np.nan)-control.get("cumulative_r",np.nan),
            "return_per_slot_uplift":challenger.get("return_per_slot",np.nan)-control.get("return_per_slot",np.nan),
            "drawdown_delta_r":challenger.get("max_cumulative_r_drawdown",np.nan)-control.get("max_cumulative_r_drawdown",np.nan),
            "positive_month_fraction_delta":challenger.get("positive_month_fraction",np.nan)-control.get("positive_month_fraction",np.nan),
            "worst_month_delta_r":challenger.get("worst_month_r",np.nan)-control.get("worst_month_r",np.nan),
        },
        "gate_results":gates,
        "frozen_gates":protocol["frozen_gates"],
        "production_authority_effect":False,
        "next_step":"REVIEW PROSPECTIVE VERDICT; NO AUTOMATIC PRODUCTION PROMOTION",
    }
    _atomic_json(_resolve(root,cfg.summary_path),out)
    return out

def status(cfg:CapacityAwareShadowConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    pp=_resolve(root,cfg.protocol_path)
    sd=_resolve(root,cfg.snapshot_dir)
    md=_resolve(root,cfg.matured_dir)
    return {
        "version":VERSION,
        "binding_version":BINDING_VERSION,
        "protocol_id":PROTOCOL_ID,
        "protocol_frozen":pp.exists(),
        "snapshot_count":len(list(sd.glob("*.json"))) if sd.exists() else 0,
        "matured_snapshot_count":len(list(md.glob("*.json"))) if md.exists() else 0,
        "live_candidate_binding_present":_resolve(root,cfg.live_candidate_snapshot_path).exists(),
        "live_capacity_binding_present":_resolve(root,cfg.live_capacity_state_path).exists(),
        "production_authority_effect":False,
    }

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.40 frozen prospective capacity-aware capital allocation shadow certification")
    p.add_argument("--project-root",required=True)
    p.add_argument("--action",required=True,choices=("freeze","bind","record","update","evaluate","status"))
    p.add_argument("--portfolio-id",default=DEFAULT_PORTFOLIO_ID)
    return p

def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    cfg=CapacityAwareShadowConfig(project_root=a.project_root,portfolio_id=a.portfolio_id,auto_bind_live_authority=True)
    if a.action=="freeze": out=freeze_protocol(cfg)
    elif a.action=="bind": out=bind_live_inputs(cfg)
    elif a.action=="record": out=record_snapshot(cfg)
    elif a.action=="update": out=update_matured(cfg)
    elif a.action=="evaluate": out=evaluate(cfg)
    else: out=status(cfg)
    print(json.dumps(out,indent=2,sort_keys=True,default=_json_default))
    return 0
