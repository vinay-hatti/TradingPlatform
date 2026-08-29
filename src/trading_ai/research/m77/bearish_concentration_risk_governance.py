from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from trading_ai.research.m77.edge_discovery_lab import EdgeLabError, _json_default, sanitize_nonfinite_numeric
from trading_ai.research.m77.bearish_deterioration_lab import DEVELOPMENT_END, HORIZONS

VERSION = "M77.22.2-BEARISH-CONCENTRATION-RISK-GOVERNANCE-1.0"
PRIMARY_TAIL = 0.01
EXCLUSION_COUNTS = (0, 1, 5, 10, 20)
COOLDOWN_MULTIPLIER = 7.0 / 5.0


@dataclass(frozen=True)
class BearishConcentrationConfig:
    project_root: str
    development_predictions: str = "research_data/m77_21_2/multivariate_predictive_tail_lab/walk_forward_predictions.csv.gz"
    integrity_evidence: str = "research_data/m77_21_2_1/historical_price_integrity_lab/prediction_integrity_evidence.csv.gz"
    development_panel: str = "research_data/m77_21_0/edge_discovery_lab/checkpoints/panel.pkl.gz"
    output_root: str = "research_data/m77_22_2/bearish_concentration_risk_governance"
    horizons: tuple[int, ...] = HORIZONS
    primary_tail: float = PRIMARY_TAIL
    execution_mode: str = "DEVELOPMENT_ONLY_BEARISH_CONCENTRATION_RISK_GOVERNANCE"

    def validate(self) -> None:
        if self.execution_mode != "DEVELOPMENT_ONLY_BEARISH_CONCENTRATION_RISK_GOVERNANCE":
            raise EdgeLabError("M77.22.2 authorizes Development-only bearish concentration/risk-governance research")
        if tuple(self.horizons) != HORIZONS or not math.isclose(self.primary_tail, PRIMARY_TAIL):
            raise EdgeLabError("M77.22.2 frozen horizons/tail changed")
        for raw in (self.development_predictions, self.integrity_evidence, self.development_panel, self.output_root):
            low = raw.lower()
            if "m77_21_3" in low or "validation" in low or "final_holdout" in low:
                raise EdgeLabError("M77.22.2 may not read consumed Validation or Final Holdout artifacts")


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


def _load_predictions(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise EdgeLabError(f"Development predictions missing: {path}")
    df = pd.read_csv(path, compression="gzip", low_memory=False)
    df["as_of"] = pd.to_datetime(df["as_of"], errors="coerce")
    df = df.dropna(subset=["symbol", "as_of", "horizon", "probability_up"]).copy()
    df = df[df["horizon"].isin(HORIZONS)].copy()
    if df.empty or df["as_of"].max() > DEVELOPMENT_END:
        raise EdgeLabError("M77.22.2 Development predictions are empty or cross 2017-12-31")
    if "test_year" in df.columns and pd.to_numeric(df["test_year"], errors="coerce").max() > 2017:
        raise EdgeLabError("M77.22.2 predictions contain post-2017 rows")
    df, _ = sanitize_nonfinite_numeric(df)
    return df.sort_values(["as_of", "horizon", "symbol"]).reset_index(drop=True)


def _load_integrity(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise EdgeLabError(f"Integrity evidence missing: {path}")
    df = pd.read_csv(path, compression="gzip", low_memory=False)
    needed = {"symbol", "as_of", "horizon", "raw_authority_present", "interval_integrity_clean", "source_return_matches_raw", "interval_integrity_event_count"}
    missing = needed - set(df.columns)
    if missing:
        raise EdgeLabError(f"integrity evidence missing columns: {sorted(missing)}")
    df["as_of"] = pd.to_datetime(df["as_of"], errors="coerce")
    df = df.dropna(subset=["symbol", "as_of", "horizon"]).copy()
    if df["as_of"].max() > DEVELOPMENT_END:
        raise EdgeLabError("integrity evidence crosses Development boundary")
    df["integrity_clean_strict"] = (
        df["raw_authority_present"].fillna(False).astype(bool)
        & df["interval_integrity_clean"].fillna(False).astype(bool)
        & df["source_return_matches_raw"].fillna(False).astype(bool)
        & pd.to_numeric(df["interval_integrity_event_count"], errors="coerce").fillna(1).eq(0)
    )
    return df[["symbol", "as_of", "horizon", "integrity_clean_strict"]]


def _load_panel(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise EdgeLabError(f"Development panel missing: {path}")
    df = pd.read_pickle(path, compression="gzip")
    df["as_of"] = pd.to_datetime(df["as_of"], errors="coerce")
    df = df.dropna(subset=["symbol", "as_of"]).copy()
    if df["as_of"].max() > DEVELOPMENT_END:
        raise EdgeLabError("panel crosses Development boundary")
    return df


def _annotate(pred: pd.DataFrame, integ: pd.DataFrame) -> pd.DataFrame:
    out = pred.merge(integ, on=["symbol", "as_of", "horizon"], how="left", validate="one_to_one")
    out["integrity_clean_strict"] = out["integrity_clean_strict"].fillna(False).astype(bool)
    return out


def _select_bottom_tail(df: pd.DataFrame, horizon: int, tail: float = PRIMARY_TAIL) -> pd.DataFrame:
    d = df[df["horizon"] == horizon].copy()
    chunks: list[pd.DataFrame] = []
    for _, g in d.groupby("as_of", sort=False):
        k = max(1, int(math.ceil(len(g) * tail)))
        chunks.append(g.nsmallest(k, "probability_up"))
    return pd.concat(chunks, ignore_index=True) if chunks else d.iloc[0:0].copy()


def _clean_tail(annotated: pd.DataFrame, horizon: int) -> pd.DataFrame:
    rcol = f"fwd_ret_{horizon}"
    if rcol not in annotated.columns:
        return annotated.iloc[0:0].copy()
    d = _select_bottom_tail(annotated, horizon)
    d["raw_return"] = pd.to_numeric(d[rcol], errors="coerce")
    d = d[d["integrity_clean_strict"] & np.isfinite(d["raw_return"])].copy()
    d["signed_return"] = -d["raw_return"]
    d["short_win"] = d["raw_return"] < 0
    return d


def _stats(d: pd.DataFrame) -> dict[str, Any]:
    if d.empty:
        return {
            "n": 0, "unique_symbols": 0, "selection_dates": 0,
            "short_win_rate": np.nan, "mean_signed_return": np.nan, "median_signed_return": np.nan,
            "equal_symbol_mean_signed_return": np.nan, "equal_symbol_positive_fraction": np.nan,
            "positive_years": 0, "years": 0,
        }
    by_symbol = d.groupby("symbol")["signed_return"].mean()
    by_year = d.groupby(d["as_of"].dt.year)["signed_return"].mean()
    return {
        "n": int(len(d)),
        "unique_symbols": int(d["symbol"].nunique()),
        "selection_dates": int(d["as_of"].nunique()),
        "short_win_rate": float(d["short_win"].mean()),
        "mean_signed_return": float(d["signed_return"].mean()),
        "median_signed_return": float(d["signed_return"].median()),
        "equal_symbol_mean_signed_return": float(by_symbol.mean()),
        "equal_symbol_positive_fraction": float((by_symbol > 0).mean()),
        "positive_years": int((by_year > 0).sum()),
        "years": int(len(by_year)),
    }


def _top_contributor_symbols(d: pd.DataFrame, count: int) -> list[str]:
    if count <= 0 or d.empty:
        return []
    contrib = d.groupby("symbol")["signed_return"].sum().abs().sort_values(ascending=False)
    return [str(x) for x in contrib.head(count).index]


def _exclusion_stress(annotated: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for h in HORIZONS:
        d = _clean_tail(annotated, h)
        if d.empty:
            continue
        for nremove in EXCLUSION_COUNTS:
            removed = _top_contributor_symbols(d, nremove)
            kept = d[~d["symbol"].astype(str).isin(removed)].copy()
            st = _stats(kept)
            rows.append({"horizon": h, "removed_top_contributor_symbols": nremove, "removed_symbols": ";".join(removed), **st})
    return pd.DataFrame(rows)


def _nonoverlap_symbol_filter(d: pd.DataFrame, horizon: int) -> pd.DataFrame:
    if d.empty:
        return d.copy()
    cooldown_days = int(math.ceil(horizon * COOLDOWN_MULTIPLIER))
    keep_idx: list[int] = []
    for _, g in d.sort_values(["symbol", "as_of"]).groupby("symbol", sort=False):
        last: pd.Timestamp | None = None
        for idx, row in g.iterrows():
            ts = pd.Timestamp(row["as_of"])
            if last is None or (ts - last).days >= cooldown_days:
                keep_idx.append(idx)
                last = ts
    return d.loc[keep_idx].sort_values(["as_of", "symbol"]).copy()


def _repeat_selection_stress(annotated: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for h in HORIZONS:
        d=_clean_tail(annotated,h)
        if d.empty: continue
        filtered=_nonoverlap_symbol_filter(d,h)
        rows.append({"horizon":h,"mode":"ALL_SELECTIONS",**_stats(d)})
        rows.append({"horizon":h,"mode":"NONOVERLAPPING_PER_SYMBOL",**_stats(filtered),"retained_fraction":float(len(filtered)/len(d))})
    return pd.DataFrame(rows)


def _contributor_decomposition(annotated: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for h in HORIZONS:
        d=_clean_tail(annotated,h)
        if d.empty: continue
        agg=(d.groupby("symbol").agg(observations=("symbol","size"),mean_signed_return=("signed_return","mean"),sum_signed_return=("signed_return","sum"),short_win_rate=("short_win","mean"),first_as_of=("as_of","min"),last_as_of=("as_of","max")).reset_index())
        agg["abs_contribution"] = agg["sum_signed_return"].abs()
        den=float(agg["abs_contribution"].sum())
        agg["abs_contribution_fraction"] = agg["abs_contribution"]/den if den else np.nan
        agg["horizon"]=h
        agg=agg.sort_values("abs_contribution",ascending=False)
        agg["contribution_rank"]=np.arange(1,len(agg)+1)
        rows.append(agg)
    return pd.concat(rows,ignore_index=True) if rows else pd.DataFrame()


def _severe_loss_capture(annotated: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for h in HORIZONS:
        rcol=f"fwd_ret_{h}"
        base=annotated[(annotated.horizon==h)&annotated.integrity_clean_strict].copy()
        if rcol not in base.columns or base.empty: continue
        base["ret"]=pd.to_numeric(base[rcol],errors="coerce")
        base=base[np.isfinite(base.ret)].copy()
        tail=_clean_tail(annotated,h)
        if tail.empty: continue
        tail_keys=tail[["symbol","as_of"]].drop_duplicates().assign(_in_tail=True)
        base=base.merge(tail_keys,on=["symbol","as_of"],how="left")
        in_tail=base["_in_tail"].eq(True)
        for threshold in (-0.05,-0.10,-0.20):
            sev=base.ret<=threshold
            total=int(sev.sum()); captured=int((sev&in_tail).sum())
            frac=float(in_tail.mean())
            rows.append({"horizon":h,"loss_threshold":threshold,"population_n":len(base),"tail_n":int(in_tail.sum()),"tail_fraction":frac,"severe_losses":total,"severe_losses_captured":captured,"capture_fraction":float(captured/total) if total else np.nan,"capture_lift_vs_random":float((captured/total)/frac) if total and frac else np.nan})
    return pd.DataFrame(rows)


def _find_candidate_flag_columns(panel: pd.DataFrame) -> list[str]:
    keywords=("candidate","eligible","actionable","qualified","ready","recommend","bullish")
    out=[]
    for c in panel.columns:
        low=str(c).lower()
        if any(k in low for k in keywords):
            s=panel[c]
            if s.dtype==bool or s.dropna().nunique()<=12:
                out.append(c)
    return out[:40]


def _truthy_mask(s: pd.Series) -> pd.Series:
    if s.dtype==bool:
        return s.fillna(False)
    vals=s.astype(str).str.upper().str.strip()
    return vals.isin({"TRUE","1","YES","Y","ELIGIBLE","READY","ACTIONABLE","BULLISH","PASS","PASSED","QUALIFIED"})


def _candidate_long_veto(annotated: pd.DataFrame, panel: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    flags=_find_candidate_flag_columns(panel)
    audit=pd.DataFrame({"candidate_flag_column":flags})
    if not flags:
        return pd.DataFrame(), audit
    base_panel=panel[["symbol","as_of",*flags]].copy()
    rows=[]
    for flag in flags:
        pmask=_truthy_mask(base_panel[flag])
        eligible=base_panel.loc[pmask,["symbol","as_of"]].drop_duplicates()
        if len(eligible)<250:
            continue
        for h in HORIZONS:
            rcol=f"fwd_ret_{h}"
            d=annotated[(annotated.horizon==h)&annotated.integrity_clean_strict].copy()
            if rcol not in d.columns: continue
            d=d.merge(eligible,on=["symbol","as_of"],how="inner")
            d["ret"]=pd.to_numeric(d[rcol],errors="coerce")
            d=d[np.isfinite(d.ret)].copy()
            if len(d)<250: continue
            tail=_clean_tail(annotated,h)[["symbol","as_of"]].drop_duplicates()
            veto=d.merge(tail.assign(veto=True),on=["symbol","as_of"],how="left")
            veto["veto"]=veto["veto"].eq(True)
            kept=veto[~veto.veto]; removed=veto[veto.veto]
            if removed.empty: continue
            rows.append({
                "candidate_flag_column":flag,"horizon":h,"candidate_n":len(veto),"vetoed_n":len(removed),"veto_fraction":float(len(removed)/len(veto)),
                "baseline_loss_rate":float((veto.ret<0).mean()),"post_veto_loss_rate":float((kept.ret<0).mean()),"loss_rate_improvement":float((veto.ret<0).mean()-(kept.ret<0).mean()),
                "baseline_severe_loss_rate":float((veto.ret<=-0.10).mean()),"post_veto_severe_loss_rate":float((kept.ret<=-0.10).mean()),"severe_loss_rate_improvement":float((veto.ret<=-0.10).mean()-(kept.ret<=-0.10).mean()),
                "baseline_mean_return":float(veto.ret.mean()),"post_veto_mean_return":float(kept.ret.mean()),"mean_return_improvement":float(kept.ret.mean()-veto.ret.mean()),
                "vetoed_mean_return":float(removed.ret.mean()),"vetoed_median_return":float(removed.ret.median()),
            })
    return pd.DataFrame(rows), audit


def _metadata_audit(project_root: Path, symbols: Iterable[str]) -> pd.DataFrame:
    # Fail closed: only report metadata that can be discovered locally; never infer asset class/sector from ticker text.
    candidates=[]
    for p in project_root.rglob("*.csv"):
        low=p.name.lower()
        if any(k in low for k in ("universe","symbol","sector","membership")) and "research_data" not in str(p):
            candidates.append(p)
    rows=[]
    for p in candidates[:50]:
        try:
            head=pd.read_csv(p,nrows=5)
        except Exception:
            continue
        symcols=[c for c in head.columns if str(c).lower() in {"symbol","ticker"}]
        if symcols:
            rows.append({"path":str(p.relative_to(project_root)),"symbol_column":symcols[0],"columns":";".join(map(str,head.columns))})
    if not rows:
        rows=[{"path":"NOT_AVAILABLE","symbol_column":"","columns":"Sector/ETF metadata unavailable; no classifications inferred"}]
    return pd.DataFrame(rows)


def _readiness(exclusion: pd.DataFrame, repeats: pd.DataFrame, capture: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for h in HORIZONS:
        ex=exclusion[(exclusion.horizon==h)&(exclusion.removed_top_contributor_symbols==10)]
        rp=repeats[(repeats["horizon"]==h)&(repeats["mode"]=="NONOVERLAPPING_PER_SYMBOL")]
        cp=capture[(capture.horizon==h)&(capture.loss_threshold==-0.10)]
        if ex.empty or rp.empty or cp.empty: continue
        e=ex.iloc[0]; r=rp.iloc[0]; c=cp.iloc[0]
        gates={
            "win_after_top10_removal": float(e.short_win_rate)>=0.54,
            "positive_equal_symbol_mean": float(e.equal_symbol_mean_signed_return)>0,
            "positive_symbol_fraction": float(e.equal_symbol_positive_fraction)>=0.50,
            "nonoverlap_win_rate": float(r.short_win_rate)>=0.54,
            "nonoverlap_mean_positive": float(r.mean_signed_return)>0,
            "severe_loss_capture_lift": float(c.capture_lift_vs_random)>=2.0,
        }
        rows.append({"horizon":h,**gates,"passes_deconcentrated_risk_governance_readiness":all(gates.values())})
    return pd.DataFrame(rows)


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a small DataFrame as Markdown without optional tabulate dependency."""
    if frame is None or frame.empty:
        return ""
    cols = [str(c) for c in frame.columns]
    def cell(value: Any) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, (float, np.floating)):
            text = f"{float(value):.6g}"
        else:
            text = str(value)
        return text.replace("\n", " ").replace("|", "\\|")
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(cell(v) for v in row) + " |")
    return "\n".join(lines)


def _write_report(out: Path, summary: dict[str,Any], ready: pd.DataFrame, veto: pd.DataFrame) -> None:
    lines=["# M77.22.2 Bearish Concentration Decomposition & Risk-Governance Edge Research","",f"Status: **{summary['status']}**","",f"Deconcentrated readiness horizons: **{summary['deconcentrated_readiness_horizons']}**","","Final Holdout remains sealed. Validation 2018-2022 is not read.",""]
    if not ready.empty:
        lines += ["## Development-only readiness","",_markdown_table(ready),""]
    if not veto.empty:
        best=veto.sort_values(["severe_loss_rate_improvement","mean_return_improvement"],ascending=False).head(10)
        lines += ["## Candidate-long veto evidence","",_markdown_table(best),""]
    else:
        lines += ["## Candidate-long veto evidence","","No sufficiently populated boolean/categorical candidate flag was discoverable in the cached panel. This is reported as unavailable rather than inferred.",""]
    (out/"BEARISH_CONCENTRATION_RISK_GOVERNANCE_REPORT.md").write_text("\n".join(lines),encoding="utf-8")


def run_lab(cfg: BearishConcentrationConfig) -> dict[str,Any]:
    cfg.validate(); root=Path(cfg.project_root).expanduser().resolve(); out=_resolve(root,cfg.output_root); out.mkdir(parents=True,exist_ok=True)
    pred=_load_predictions(_resolve(root,cfg.development_predictions)); integ=_load_integrity(_resolve(root,cfg.integrity_evidence)); panel=_load_panel(_resolve(root,cfg.development_panel)); ann=_annotate(pred,integ)
    contrib=_contributor_decomposition(ann); exclusion=_exclusion_stress(ann); repeats=_repeat_selection_stress(ann); capture=_severe_loss_capture(ann); veto,audit=_candidate_long_veto(ann,panel); metadata=_metadata_audit(root,ann.symbol.unique()); ready=_readiness(exclusion,repeats,capture)
    _atomic_csv(out/"bearish_symbol_contribution_decomposition.csv",contrib)
    _atomic_csv(out/"bearish_top_contributor_exclusion_stress.csv",exclusion)
    _atomic_csv(out/"bearish_repeat_selection_stress.csv",repeats)
    _atomic_csv(out/"bearish_severe_loss_capture_evidence.csv",capture)
    _atomic_csv(out/"candidate_long_bearish_veto_evidence.csv",veto)
    _atomic_csv(out/"candidate_flag_discovery_audit.csv",audit)
    _atomic_csv(out/"local_symbol_metadata_audit.csv",metadata)
    _atomic_csv(out/"deconcentrated_risk_governance_readiness.csv",ready)
    summary={
        "version":VERSION,"status":"COMPLETE","completed_at":datetime.now(timezone.utc).isoformat(),"development_boundary":"2017-12-31",
        "prediction_rows":int(len(pred)),"symbols":int(pred.symbol.nunique()),"integrity_clean_fraction":float(ann.integrity_clean_strict.mean()),
        "deconcentrated_readiness_horizons":int(ready.passes_deconcentrated_risk_governance_readiness.sum()) if not ready.empty else 0,
        "candidate_veto_evidence_rows":int(len(veto)),"candidate_flag_columns_discovered":int(len(audit)),
        "validation_partition_opened":False,"validation_rows_read":0,"consumed_validation_reused_for_tuning":False,"final_holdout_opened":False,"final_holdout_rows_read":0,
        "polygon_api_called":False,"production_authority_effect":False,
        "next_step":"REVIEW_DECONCENTRATED_BEARISH_RISK_GOVERNANCE_EVIDENCE_BEFORE_ANY_FINAL_HOLDOUT_PROTOCOL_DECISION",
    }
    _atomic_json(out/"bearish_concentration_risk_governance_summary.json",summary)
    _atomic_json(out/"run_manifest.json",{"version":VERSION,"config":asdict(cfg),"summary":summary})
    _write_report(out,summary,ready,veto)
    return summary


def build_parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.22.2 Bearish Concentration Decomposition & Risk-Governance Edge Research")
    p.add_argument("--project-root",required=True)
    return p


def main(argv: list[str] | None=None) -> int:
    args=build_parser().parse_args(argv); summary=run_lab(BearishConcentrationConfig(project_root=args.project_root)); print(json.dumps(summary,indent=2,sort_keys=True,default=_json_default)); return 0
