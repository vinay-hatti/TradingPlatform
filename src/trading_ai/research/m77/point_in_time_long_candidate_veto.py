from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from trading_ai.research.m77.edge_discovery_lab import EdgeLabError, _json_default, sanitize_nonfinite_numeric
from trading_ai.research.m77.bearish_deterioration_lab import DEVELOPMENT_END, HORIZONS
from trading_ai.research.m77.bearish_concentration_risk_governance import _load_integrity, _load_predictions, _annotate, _markdown_table

VERSION = "M77.22.3-PIT-LONG-CANDIDATE-DOWNSIDE-RISK-VETO-1.0"
TAILS = (0.01, 0.025, 0.05)
ERAS = ((2008, 2010, "2008_2010"), (2011, 2013, "2011_2013"), (2014, 2017, "2014_2017"))


@dataclass(frozen=True)
class LongCandidateVetoConfig:
    project_root: str
    pit_profiles_root: str = "research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay/weekly/profiles"
    development_predictions: str = "research_data/m77_21_2/multivariate_predictive_tail_lab/walk_forward_predictions.csv.gz"
    integrity_evidence: str = "research_data/m77_21_2_1/historical_price_integrity_lab/prediction_integrity_evidence.csv.gz"
    output_root: str = "research_data/m77_22_3/point_in_time_long_candidate_veto"
    execution_mode: str = "DEVELOPMENT_ONLY_PIT_LONG_CANDIDATE_DOWNSIDE_RISK_VETO"
    horizons: tuple[int, ...] = HORIZONS
    tails: tuple[float, ...] = TAILS

    def validate(self) -> None:
        if self.execution_mode != "DEVELOPMENT_ONLY_PIT_LONG_CANDIDATE_DOWNSIDE_RISK_VETO":
            raise EdgeLabError("M77.22.3 authorizes only Development-era PIT long-candidate veto research")
        if tuple(self.horizons) != HORIZONS or tuple(self.tails) != TAILS:
            raise EdgeLabError("M77.22.3 frozen horizons/tails changed")
        for raw in (self.pit_profiles_root, self.development_predictions, self.integrity_evidence, self.output_root):
            low = raw.lower()
            if "m77_21_3" in low or "validation" in low or "final_holdout" in low:
                raise EdgeLabError("M77.22.3 may not read consumed Validation or Final Holdout artifacts")


def _resolve(root: Path, raw: str) -> Path:
    p = Path(raw).expanduser()
    return p.resolve() if p.is_absolute() else (root / p).resolve()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True, default=_json_default)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _atomic_csv(path: Path, frame: pd.DataFrame, compression: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp, index=False, compression=compression)
    os.replace(tmp, path)


def _str(v: Any) -> str:
    return str(v or "").strip().upper()


def _num(v: Any) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else np.nan
    except (TypeError, ValueError):
        return np.nan


def _is_bullish(direction: Any) -> bool:
    d = _str(direction)
    return "BULL" in d and "BEAR" not in d


def _extract_profile_record(obj: dict[str, Any]) -> dict[str, Any] | None:
    as_of = pd.to_datetime(obj.get("as_of"), errors="coerce")
    if pd.isna(as_of) or as_of > DEVELOPMENT_END:
        return None
    p = obj.get("profile") or {}
    scores = p.get("scores") or {}
    idi = p.get("decision_intelligence") or {}
    trade_plan = p.get("trade_plan") or {}
    cert = trade_plan.get("certification") or {}
    entry_exec = cert.get("entry_execution") or {}
    direction = p.get("direction") or obj.get("direction")
    native_direction = obj.get("direction") or direction
    decision = idi.get("decision")
    lifecycle = idi.get("opportunity_lifecycle")
    cert_status = cert.get("status")
    trade_builder_ready = bool(cert.get("trade_builder_ready") or entry_exec.get("trade_builder_ready"))
    bullish = _is_bullish(direction)

    return {
        "symbol": str(obj.get("symbol") or p.get("symbol") or "").upper(),
        "as_of": as_of,
        "native_direction": _str(native_direction),
        "profile_direction": _str(direction),
        "profile_confidence": _num(p.get("confidence", obj.get("confidence"))),
        "overall_score": _num(p.get("overall_score", obj.get("overall_score"))),
        "score_overall": _num(scores.get("overall")),
        "score_bullish": _num(scores.get("bullish")),
        "score_bearish": _num(scores.get("bearish")),
        "score_confidence": _num(scores.get("confidence")),
        "score_options_suitability": _num(scores.get("options_suitability")),
        "primary_category": _str(scores.get("primary_category")),
        "idi_decision": _str(decision),
        "idi_readiness": _num(idi.get("decision_readiness")),
        "idi_trade_quality": _num(idi.get("overall_trade_quality")),
        "idi_capital_priority": _num(idi.get("capital_priority")),
        "idi_grade": _str(idi.get("institutional_grade")),
        "idi_lifecycle": _str(lifecycle),
        "cert_status": _str(cert_status),
        "cert_publishable": bool(cert.get("publishable", False)),
        "trade_builder_ready": trade_builder_ready,
        "profile_structure": _str(p.get("structure")),
        "native_bullish_direction": bullish,
        "pop_native_bullish": bullish,
        "pop_primary_category_bullish": bullish and _str(scores.get("primary_category")) == "BULLISH",
        "pop_idi_eligible_or_prioritize": bullish and _str(decision) in {"ELIGIBLE", "PRIORITIZE"},
        "pop_idi_prioritize": bullish and _str(decision) == "PRIORITIZE",
        "pop_lifecycle_actionable": bullish and _str(lifecycle) == "ACTIONABLE",
        "pop_certified_trade_builder_ready": bullish and _str(cert_status) == "PASS" and trade_builder_ready,
    }


def reconstruct_long_candidate_authority(profiles_root: Path, out_root: Path) -> pd.DataFrame:
    if not profiles_root.exists():
        raise EdgeLabError(f"PIT profile authority missing: {profiles_root}")
    checkpoint = out_root / "checkpoints" / "pit_long_candidate_authority.csv.gz"
    meta = out_root / "checkpoints" / "pit_long_candidate_authority_meta.json"
    files = sorted(profiles_root.glob("*.jsonl.gz"))
    if not files:
        raise EdgeLabError(f"No PIT profile files found under {profiles_root}")
    signature = hashlib.sha256("\n".join(f"{p.name}:{p.stat().st_size}:{int(p.stat().st_mtime)}" for p in files).encode()).hexdigest()
    if checkpoint.exists() and meta.exists():
        try:
            m = json.loads(meta.read_text())
            if m.get("source_signature") == signature:
                df = pd.read_csv(checkpoint, compression="gzip", low_memory=False)
                df["as_of"] = pd.to_datetime(df["as_of"], errors="coerce")
                return df
        except Exception:
            pass

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for path in files:
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                for line_no, line in enumerate(fh, start=1):
                    if not line.strip():
                        continue
                    try:
                        rec = _extract_profile_record(json.loads(line))
                    except Exception as exc:
                        failures.append({"file": path.name, "line": str(line_no), "error": repr(exc)})
                        continue
                    if rec and rec["symbol"]:
                        rows.append(rec)
        except Exception as exc:
            failures.append({"file": path.name, "line": "", "error": repr(exc)})
    if not rows:
        raise EdgeLabError("PIT long-candidate reconstruction produced no Development rows")
    df = pd.DataFrame(rows).drop_duplicates(["symbol", "as_of"], keep="last")
    df = df[df["as_of"] <= DEVELOPMENT_END].sort_values(["as_of", "symbol"]).reset_index(drop=True)
    # Contemporaneous top-decile opportunity score is a research population, clearly separated from native states.
    score = pd.to_numeric(df["score_overall"], errors="coerce")
    df["score_overall_rank_pct"] = score.groupby(df["as_of"]).rank(method="average", pct=True)
    df["pop_bullish_top_decile_score"] = df["native_bullish_direction"].fillna(False).astype(bool) & df["score_overall_rank_pct"].ge(0.90)
    _atomic_csv(checkpoint, df, compression="gzip")
    _atomic_json(meta, {"source_signature": signature, "source_files": len(files), "rows": len(df), "failures": len(failures), "version": VERSION})
    _atomic_csv(out_root / "pit_profile_parse_failures.csv", pd.DataFrame(failures))
    return df


def _candidate_columns(frame: pd.DataFrame) -> list[str]:
    return [c for c in frame.columns if c.startswith("pop_") and frame[c].dtype == bool]


def _select_bearish_tail(ann: pd.DataFrame, horizon: int, tail: float) -> pd.DataFrame:
    d = ann[ann["horizon"] == horizon].copy()
    parts = []
    for _, g in d.groupby("as_of", sort=False):
        k = max(1, int(math.ceil(len(g) * tail)))
        parts.append(g.nsmallest(k, "probability_up"))
    return pd.concat(parts, ignore_index=True) if parts else d.iloc[0:0].copy()


def _metrics(d: pd.DataFrame, ret_col: str, horizon: int) -> dict[str, Any]:
    if d.empty:
        return {"n": 0, "symbols": 0, "dates": 0, "win_rate": np.nan, "mean_return": np.nan, "median_return": np.nan,
                "loss_rate": np.nan, "loss_5_rate": np.nan, "loss_10_rate": np.nan, "loss_20_rate": np.nan,
                "mean_mfe_atr": np.nan, "mean_mae_atr": np.nan}
    r = pd.to_numeric(d[ret_col], errors="coerce")
    valid = d.loc[np.isfinite(r)].copy()
    r = pd.to_numeric(valid[ret_col], errors="coerce")
    mfe = pd.to_numeric(valid.get(f"mfe_atr_{horizon}"), errors="coerce") if f"mfe_atr_{horizon}" in valid.columns else pd.Series(dtype=float)
    mae = pd.to_numeric(valid.get(f"mae_atr_{horizon}"), errors="coerce") if f"mae_atr_{horizon}" in valid.columns else pd.Series(dtype=float)
    return {
        "n": int(len(valid)), "symbols": int(valid["symbol"].nunique()), "dates": int(valid["as_of"].nunique()),
        "win_rate": float((r > 0).mean()) if len(r) else np.nan,
        "mean_return": float(r.mean()) if len(r) else np.nan,
        "median_return": float(r.median()) if len(r) else np.nan,
        "loss_rate": float((r < 0).mean()) if len(r) else np.nan,
        "loss_5_rate": float((r <= -0.05).mean()) if len(r) else np.nan,
        "loss_10_rate": float((r <= -0.10).mean()) if len(r) else np.nan,
        "loss_20_rate": float((r <= -0.20).mean()) if len(r) else np.nan,
        "mean_mfe_atr": float(mfe[np.isfinite(mfe)].mean()) if len(mfe) and np.isfinite(mfe).any() else np.nan,
        "mean_mae_atr": float(mae[np.isfinite(mae)].mean()) if len(mae) and np.isfinite(mae).any() else np.nan,
    }


def evaluate_veto(ann: pd.DataFrame, authority: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candidates = _candidate_columns(authority)
    if not candidates:
        raise EdgeLabError("No reconstructed PIT long-candidate populations available")
    base_auth = authority[["symbol", "as_of", *candidates]].copy()
    rows: list[dict[str, Any]] = []
    era_rows: list[dict[str, Any]] = []
    capture_rows: list[dict[str, Any]] = []

    for pop in candidates:
        keys = base_auth.loc[base_auth[pop].fillna(False).astype(bool), ["symbol", "as_of"]].drop_duplicates()
        if keys.empty:
            continue
        for h in HORIZONS:
            ret_col = f"fwd_ret_{h}"
            if ret_col not in ann.columns:
                continue
            clean = ann[(ann["horizon"] == h) & ann["integrity_clean_strict"]].merge(keys, on=["symbol", "as_of"], how="inner")
            clean[ret_col] = pd.to_numeric(clean[ret_col], errors="coerce")
            clean = clean[np.isfinite(clean[ret_col])].copy()
            if clean.empty:
                continue
            for tail in TAILS:
                tail_keys = _select_bearish_tail(ann, h, tail)[["symbol", "as_of"]].drop_duplicates().assign(veto=True)
                tagged = clean.merge(tail_keys, on=["symbol", "as_of"], how="left")
                tagged["veto"] = tagged["veto"].eq(True)
                kept = tagged[~tagged["veto"]].copy()
                vetoed = tagged[tagged["veto"]].copy()
                if vetoed.empty:
                    continue
                b = _metrics(tagged, ret_col, h); k = _metrics(kept, ret_col, h); v = _metrics(vetoed, ret_col, h)
                severe_total = int((pd.to_numeric(tagged[ret_col]) <= -0.10).sum())
                severe_veto = int((pd.to_numeric(vetoed[ret_col]) <= -0.10).sum())
                veto_frac = len(vetoed) / len(tagged)
                severe_capture = severe_veto / severe_total if severe_total else np.nan
                lift = severe_capture / veto_frac if severe_total and veto_frac else np.nan
                row = {
                    "population": pop, "horizon": h, "tail_fraction": tail,
                    "candidate_n": b["n"], "candidate_symbols": b["symbols"], "veto_n": v["n"], "veto_symbols": v["symbols"], "veto_fraction": veto_frac,
                    "baseline_win_rate": b["win_rate"], "post_veto_win_rate": k["win_rate"], "win_rate_improvement": k["win_rate"] - b["win_rate"],
                    "baseline_mean_return": b["mean_return"], "post_veto_mean_return": k["mean_return"], "mean_return_improvement": k["mean_return"] - b["mean_return"],
                    "baseline_median_return": b["median_return"], "post_veto_median_return": k["median_return"], "median_return_improvement": k["median_return"] - b["median_return"],
                    "baseline_loss_10_rate": b["loss_10_rate"], "post_veto_loss_10_rate": k["loss_10_rate"], "loss_10_rate_reduction": b["loss_10_rate"] - k["loss_10_rate"],
                    "baseline_loss_20_rate": b["loss_20_rate"], "post_veto_loss_20_rate": k["loss_20_rate"], "loss_20_rate_reduction": b["loss_20_rate"] - k["loss_20_rate"],
                    "vetoed_win_rate": v["win_rate"], "vetoed_mean_return": v["mean_return"], "vetoed_median_return": v["median_return"],
                    "vetoed_loss_10_rate": v["loss_10_rate"], "vetoed_loss_20_rate": v["loss_20_rate"],
                    "baseline_mean_mfe_atr": b["mean_mfe_atr"], "post_veto_mean_mfe_atr": k["mean_mfe_atr"],
                    "baseline_mean_mae_atr": b["mean_mae_atr"], "post_veto_mean_mae_atr": k["mean_mae_atr"],
                    "severe_losses": severe_total, "severe_losses_vetoed": severe_veto, "severe_loss_capture_fraction": severe_capture,
                    "severe_loss_capture_lift_vs_random": lift,
                }
                rows.append(row)
                capture_rows.append({"population": pop, "horizon": h, "tail_fraction": tail, "candidate_n": len(tagged), "veto_n": len(vetoed),
                                     "veto_fraction": veto_frac, "severe_losses": severe_total, "severe_losses_vetoed": severe_veto,
                                     "severe_loss_capture_fraction": severe_capture, "capture_lift_vs_random": lift})
                for start, end, label in ERAS:
                    e = tagged[tagged["as_of"].dt.year.between(start, end)].copy()
                    if e.empty:
                        continue
                    ek = e[~e["veto"]].copy(); ev = e[e["veto"]].copy()
                    eb = _metrics(e, ret_col, h); em = _metrics(ek, ret_col, h)
                    era_rows.append({"population": pop, "horizon": h, "tail_fraction": tail, "era": label,
                                     "candidate_n": eb["n"], "veto_n": len(ev), "baseline_win_rate": eb["win_rate"], "post_veto_win_rate": em["win_rate"],
                                     "win_rate_improvement": em["win_rate"] - eb["win_rate"], "baseline_loss_10_rate": eb["loss_10_rate"],
                                     "post_veto_loss_10_rate": em["loss_10_rate"], "loss_10_rate_reduction": eb["loss_10_rate"] - em["loss_10_rate"],
                                     "baseline_mean_return": eb["mean_return"], "post_veto_mean_return": em["mean_return"], "mean_return_improvement": em["mean_return"] - eb["mean_return"]})
    return pd.DataFrame(rows), pd.DataFrame(era_rows), pd.DataFrame(capture_rows)


def readiness(veto: pd.DataFrame, eras: pd.DataFrame) -> pd.DataFrame:
    if veto.empty:
        return pd.DataFrame()
    rows=[]
    primary = veto[veto["tail_fraction"].eq(0.01)].copy()
    for _, r in primary.iterrows():
        er = eras[(eras["population"] == r["population"]) & (eras["horizon"] == r["horizon"]) & eras["tail_fraction"].eq(0.01)]
        positive_era_risk = int((pd.to_numeric(er["loss_10_rate_reduction"], errors="coerce") > 0).sum()) if not er.empty else 0
        gates = {
            "minimum_candidate_rows": int(r["candidate_n"]) >= 1000,
            "minimum_veto_rows": int(r["veto_n"]) >= 25,
            "minimum_veto_symbols": int(r["veto_symbols"]) >= 20,
            "severe_loss_capture_lift": float(r["severe_loss_capture_lift_vs_random"]) >= 2.0 if pd.notna(r["severe_loss_capture_lift_vs_random"]) else False,
            "post_veto_severe_loss_improves": float(r["loss_10_rate_reduction"]) > 0 if pd.notna(r["loss_10_rate_reduction"]) else False,
            "mean_return_not_degraded": float(r["mean_return_improvement"]) >= -0.001 if pd.notna(r["mean_return_improvement"]) else False,
            "win_rate_not_degraded": float(r["win_rate_improvement"]) >= -0.002 if pd.notna(r["win_rate_improvement"]) else False,
            "multi_era_risk_improvement": positive_era_risk >= 2,
        }
        rows.append({"population": r["population"], "horizon": int(r["horizon"]), **gates,
                     "passes_development_risk_governance_readiness": all(gates.values()), "positive_risk_improvement_eras": positive_era_risk})
    return pd.DataFrame(rows)


def _candidate_population_audit(authority: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for c in _candidate_columns(authority):
        d=authority[authority[c]].copy()
        rows.append({"population":c,"rows":len(d),"symbols":d.symbol.nunique(),"first_as_of":d.as_of.min(),"last_as_of":d.as_of.max(),
                     "share_of_pit_rows":float(len(d)/len(authority))})
    return pd.DataFrame(rows)


def _write_report(out: Path, summary: dict[str, Any], audit: pd.DataFrame, veto: pd.DataFrame, ready: pd.DataFrame) -> None:
    lines=["# M77.22.3 Point-in-Time Long Candidate Reconstruction & Downside-Risk Veto Research","",
           f"Status: **{summary['status']}**","",f"PIT rows reconstructed: **{summary['pit_candidate_rows']}**","",
           f"Development-ready veto configurations: **{summary['development_ready_veto_configurations']}**","",
           "2018-2022 Validation is not read. 2023+ Final Holdout remains sealed.",""]
    lines += ["## Reconstructed candidate populations","",_markdown_table(audit),""] if not audit.empty else []
    if not veto.empty:
        best=veto.sort_values(["severe_loss_capture_lift_vs_random","loss_10_rate_reduction"],ascending=False).head(20)
        lines += ["## Strongest Development-only veto evidence","",_markdown_table(best),""]
    if not ready.empty:
        lines += ["## Development risk-governance readiness","",_markdown_table(ready),""]
    lines += ["## Governance","","- Candidate populations are reconstructed from native PIT Stock Intelligence fields, not guessed from current database state.",
              "- Bearish tail membership is frozen from contemporaneous Development walk-forward probabilities before candidate intersection.",
              "- Historical integrity filtering is applied without reranking.","- No result in this phase authorizes production changes or Final Holdout use.",""]
    (out/"PIT_LONG_CANDIDATE_DOWNSIDE_RISK_VETO_REPORT.md").write_text("\n".join(lines),encoding="utf-8")


def run_lab(cfg: LongCandidateVetoConfig) -> dict[str, Any]:
    cfg.validate()
    root=Path(cfg.project_root).expanduser().resolve(); out=_resolve(root,cfg.output_root); out.mkdir(parents=True,exist_ok=True)
    authority=reconstruct_long_candidate_authority(_resolve(root,cfg.pit_profiles_root),out)
    if authority["as_of"].max()>DEVELOPMENT_END:
        raise EdgeLabError("PIT candidate authority crosses Development boundary")
    pred=_load_predictions(_resolve(root,cfg.development_predictions)); integ=_load_integrity(_resolve(root,cfg.integrity_evidence)); ann=_annotate(pred,integ)
    veto, eras, capture=evaluate_veto(ann,authority); ready=readiness(veto,eras); audit=_candidate_population_audit(authority)
    _atomic_csv(out/"pit_long_candidate_authority.csv.gz",authority,compression="gzip")
    _atomic_csv(out/"pit_long_candidate_population_audit.csv",audit)
    _atomic_csv(out/"candidate_long_bearish_veto_evidence.csv",veto)
    _atomic_csv(out/"candidate_long_bearish_veto_era_evidence.csv",eras)
    _atomic_csv(out/"candidate_long_severe_loss_capture.csv",capture)
    _atomic_csv(out/"candidate_long_veto_readiness.csv",ready)
    summary={
        "version":VERSION,"status":"COMPLETE","completed_at":datetime.now(timezone.utc).isoformat(),"development_boundary":"2017-12-31",
        "pit_candidate_rows":int(len(authority)),"pit_symbols":int(authority.symbol.nunique()),"candidate_populations":int(len(_candidate_columns(authority))),
        "prediction_rows":int(len(pred)),"integrity_clean_fraction":float(ann.integrity_clean_strict.mean()),"veto_evidence_rows":int(len(veto)),
        "development_ready_veto_configurations":int(ready.passes_development_risk_governance_readiness.sum()) if not ready.empty else 0,
        "validation_partition_opened":False,"validation_rows_read":0,"consumed_validation_reused_for_tuning":False,
        "final_holdout_opened":False,"final_holdout_rows_read":0,"polygon_api_called":False,"production_authority_effect":False,
        "next_step":"REVIEW_PIT_LONG_CANDIDATE_VETO_EVIDENCE_BEFORE_ANY_NEW_PROTOCOL_OR_PRODUCTION_DECISION",
    }
    _atomic_json(out/"point_in_time_long_candidate_veto_summary.json",summary)
    _atomic_json(out/"run_manifest.json",{"version":VERSION,"config":asdict(cfg),"summary":summary})
    _write_report(out,summary,audit,veto,ready)
    return summary


def build_parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.22.3 Point-in-Time Long Candidate Reconstruction & Downside-Risk Veto Research")
    p.add_argument("--project-root",required=True)
    return p


def main(argv: list[str] | None=None) -> int:
    args=build_parser().parse_args(argv)
    summary=run_lab(LongCandidateVetoConfig(project_root=args.project_root))
    print(json.dumps(summary,indent=2,sort_keys=True,default=_json_default))
    return 0
