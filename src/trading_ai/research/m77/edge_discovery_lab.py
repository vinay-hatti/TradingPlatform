from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import pickle
import re
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import unquote

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

VERSION = "M77.21.1.1-STATIONARITY-CONTROL-FLOW-REPAIR-1.0"
DEFAULT_DEV_END = "2017-12-31"
DEFAULT_HORIZONS = (1, 2, 3, 5, 10, 15, 20, 30, 45, 60)
DEFAULT_TARGET_STOP_GEOMETRIES = ((1.0, 1.0), (1.5, 1.0), (2.0, 1.0), (3.0, 1.0), (2.0, 1.5))
PROHIBITED_PATH_TOKENS = ("validation_target", "final_holdout", "validation_scoring", "final_holdout_scoring")


class EdgeLabError(RuntimeError):
    pass


@dataclass(frozen=True)
class LabConfig:
    project_root: str
    daily_root: str
    feature_root: str | None
    output_root: str
    cadence: str = "weekly"
    dev_end: str = DEFAULT_DEV_END
    horizons: tuple[int, ...] = DEFAULT_HORIZONS
    target_stop_geometries: tuple[tuple[float, float], ...] = DEFAULT_TARGET_STOP_GEOMETRIES
    workers: int = 4
    min_history: int = 300
    min_samples: int = 250
    top_univariate: int = 80
    top_interaction_features: int = 18
    max_pair_candidates: int = 600
    max_triple_candidates: int = 300
    include_certified_pit_features: bool = True
    include_ml_hypothesis_generation: bool = True
    resume: bool = True
    random_seed: int = 7710
    bootstrap_samples: int = 400
    execution_mode: str = "DISCOVERY_DEVELOPMENT_ONLY"

    def validate(self) -> None:
        if self.cadence not in {"daily", "weekly"}:
            raise EdgeLabError("cadence must be daily or weekly")
        if self.execution_mode != "DISCOVERY_DEVELOPMENT_ONLY":
            raise EdgeLabError("M77.21.0 only authorizes DISCOVERY_DEVELOPMENT_ONLY")
        if self.dev_end > DEFAULT_DEV_END:
            raise EdgeLabError(
                f"development boundary cannot exceed {DEFAULT_DEV_END}; validation/final holdout remain sealed"
            )
        if self.workers < 1:
            raise EdgeLabError("workers must be >= 1")
        if self.min_samples < 50:
            raise EdgeLabError("min_samples must be >= 50")
        if not self.horizons or min(self.horizons) < 1:
            raise EdgeLabError("horizons must be positive")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def _atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp, index=False)
    os.replace(tmp, path)


def _json_default(v: Any) -> Any:
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, Path):
        return str(v)
    if isinstance(v, tuple):
        return list(v)
    raise TypeError(type(v).__name__)


def _resolve(root: Path, raw: str | None) -> Path | None:
    if raw is None:
        return None
    p = Path(raw).expanduser()
    return p.resolve() if p.is_absolute() else (root / p).resolve()


def _assert_research_only_paths(config: LabConfig) -> None:
    root = Path(config.project_root).resolve()
    for label, raw in {
        "daily_root": config.daily_root,
        "feature_root": config.feature_root,
        "output_root": config.output_root,
    }.items():
        if raw is None:
            continue
        path = _resolve(root, raw)
        text = str(path).lower()
        if any(tok in text for tok in PROHIBITED_PATH_TOKENS):
            raise EdgeLabError(f"{label} points at sealed outcome/scoring path: {path}")
    out = _resolve(root, config.output_root)
    if out is None or "research_data" not in out.parts:
        raise EdgeLabError("output_root must be under research_data")


def _safe_symbol_from_filename(path: Path) -> str:
    stem = path.name[: -len(".daily.csv.gz")]
    # M77.19.7.2 encodes percent signs as underscores. Common tickers remain unchanged.
    try:
        return unquote(stem.replace("_", "%"))
    except Exception:
        return stem


def discover_daily_files(daily_root: Path) -> list[Path]:
    if not daily_root.exists():
        raise EdgeLabError(f"daily_root missing: {daily_root}")
    files = sorted(daily_root.rglob("*.daily.csv.gz"))
    if not files:
        raise EdgeLabError(f"no *.daily.csv.gz files found under {daily_root}")
    return files


def read_daily_file(path: Path, dev_end: str) -> pd.DataFrame:
    df = pd.read_csv(path, compression="gzip")
    date_col = "session_date" if "session_date" in df.columns else "date" if "date" in df.columns else None
    if date_col is None:
        raise EdgeLabError(f"{path}: missing session_date/date column")
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise EdgeLabError(f"{path}: missing columns {sorted(missing)}")
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).sort_values(date_col).drop_duplicates(date_col, keep="last")
    df = df[df[date_col] <= pd.Timestamp(dev_end)].copy()
    df = df.rename(columns={date_col: "as_of"})
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    return df.reset_index(drop=True)


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False, min_periods=span).mean()


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat(
        [(df["high"] - df["low"]).abs(), (df["high"] - prev).abs(), (df["low"] - prev).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def engineer_ohlcv_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    c, h, l, o, v = out["close"], out["high"], out["low"], out["open"], out["volume"]
    ret1 = c.pct_change()
    out["px_ret_1"] = ret1
    for n in (2, 3, 5, 10, 20, 40, 60, 126, 252):
        out[f"px_ret_{n}"] = c.pct_change(n)
    for n in (5, 10, 20, 60, 126, 252):
        sma = c.rolling(n, min_periods=n).mean()
        out[f"dist_sma_{n}"] = c / sma - 1.0
    for n in (8, 21, 50, 100, 200):
        ema = _ema(c, n)
        out[f"dist_ema_{n}"] = c / ema - 1.0
        out[f"ema_slope_{n}_5"] = ema.pct_change(5)
    out["rsi_14"] = _rsi(c, 14)
    atr = _atr(out, 14)
    out["atr_14"] = atr
    out["atr_pct_14"] = atr / c
    true_range = pd.concat([(h - l).abs(), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    out["range_atr"] = (h - l) / atr
    out["gap_atr"] = (o - c.shift(1)) / atr
    out["clv"] = ((c - l) - (h - c)) / (h - l).replace(0, np.nan)
    out["body_range"] = (c - o) / (h - l).replace(0, np.nan)
    for n in (10, 20, 60):
        out[f"rv_{n}"] = ret1.rolling(n, min_periods=n).std() * math.sqrt(252)
        vm = v.rolling(n, min_periods=n).mean()
        vs = v.rolling(n, min_periods=n).std()
        out[f"volume_ratio_{n}"] = v / vm
        out[f"volume_z_{n}"] = (v - vm) / vs.replace(0, np.nan)
    for n in (20, 60, 126, 252):
        hi = h.shift(1).rolling(n, min_periods=n).max()
        lo = l.shift(1).rolling(n, min_periods=n).min()
        out[f"dist_prev_high_{n}"] = c / hi - 1.0
        out[f"dist_prev_low_{n}"] = c / lo - 1.0
        out[f"breakout_high_{n}"] = (c > hi).astype(float)
        out[f"breakdown_low_{n}"] = (c < lo).astype(float)
    peak = c.rolling(252, min_periods=60).max()
    out["drawdown_252"] = c / peak - 1.0
    out["mom_accel_5_20"] = out["px_ret_5"] - out["px_ret_20"] / 4.0
    out["mom_accel_20_60"] = out["px_ret_20"] - out["px_ret_60"] / 3.0
    out["trend_stack_bull"] = ((c > _ema(c, 21)) & (_ema(c, 21) > _ema(c, 50)) & (_ema(c, 50) > _ema(c, 200))).astype(float)
    out["trend_stack_bear"] = ((c < _ema(c, 21)) & (_ema(c, 21) < _ema(c, 50)) & (_ema(c, 50) < _ema(c, 200))).astype(float)
    out["ret_autocorr_20"] = ret1.rolling(20, min_periods=20).corr(ret1.shift(1))
    out["up_day_fraction_20"] = (ret1 > 0).rolling(20, min_periods=20).mean()
    out["down_day_fraction_20"] = (ret1 < 0).rolling(20, min_periods=20).mean()
    return out


def _future_matrix(values: np.ndarray, horizon: int) -> np.ndarray:
    n = len(values)
    mat = np.full((n, horizon), np.nan, dtype=float)
    for j in range(1, horizon + 1):
        if j < n:
            mat[: n - j, j - 1] = values[j:]
    return mat


def _first_true_day(mask: np.ndarray) -> np.ndarray:
    any_hit = mask.any(axis=1)
    first = np.argmax(mask, axis=1).astype(float) + 1.0
    first[~any_hit] = np.inf
    return first


def add_forward_outcomes(
    df: pd.DataFrame,
    horizons: Sequence[int],
    geometries: Sequence[tuple[float, float]],
) -> pd.DataFrame:
    """Add terminal, path, and target-before-stop outcomes using only future bars.

    Same-session target+stop first hits are deliberately encoded NaN because
    daily OHLC cannot establish intraday ordering without lower-timeframe data.
    """
    out = df.copy()
    derived: dict[str, np.ndarray] = {}
    c = out["close"].to_numpy(dtype=float)
    h = out["high"].to_numpy(dtype=float)
    l = out["low"].to_numpy(dtype=float)
    atr = out["atr_14"].to_numpy(dtype=float)
    n = len(out)
    for horizon in horizons:
        future_h = _future_matrix(h, horizon)
        future_l = _future_matrix(l, horizon)
        terminal = np.full(n, np.nan, dtype=float)
        if horizon < n:
            terminal[: n - horizon] = c[horizon:]
        with np.errstate(divide="ignore", invalid="ignore"):
            derived[f"fwd_ret_{horizon}"] = terminal / c - 1.0
            delayed_terminal = np.full(n, np.nan, dtype=float)
            delayed_entry = np.full(n, np.nan, dtype=float)
            if horizon + 1 < n:
                delayed_entry[: n - horizon - 1] = c[1 : n - horizon]
                delayed_terminal[: n - horizon - 1] = c[horizon + 1 :]
            derived[f"fwd_ret_{horizon}_delay1"] = delayed_terminal / delayed_entry - 1.0
            safe_h = np.where(np.isfinite(future_h), future_h, -np.inf)
            safe_l = np.where(np.isfinite(future_l), future_l, np.inf)
            max_h = safe_h.max(axis=1)
            min_l = safe_l.min(axis=1)
            max_h[~np.isfinite(max_h)] = np.nan
            min_l[~np.isfinite(min_l)] = np.nan
            # Rows without a full terminal horizon are ineligible for every path target.
            incomplete = np.arange(n) + horizon >= n
            max_h[incomplete] = np.nan
            min_l[incomplete] = np.nan
            derived[f"mfe_{horizon}"] = max_h / c - 1.0
            derived[f"mae_{horizon}"] = min_l / c - 1.0
            derived[f"mfe_atr_{horizon}"] = (max_h - c) / atr
            derived[f"mae_atr_{horizon}"] = (min_l - c) / atr

        valid_entry = np.isfinite(c) & np.isfinite(atr) & (atr > 0) & (~incomplete)
        for target_atr, stop_atr in geometries:
            tag = f"t{str(target_atr).replace('.', 'p')}_s{str(stop_atr).replace('.', 'p')}_h{horizon}"
            lt = c + target_atr * atr
            ls = c - stop_atr * atr
            st = c - target_atr * atr
            ss = c + stop_atr * atr

            lt_day = _first_true_day(future_h >= lt[:, None])
            ls_day = _first_true_day(future_l <= ls[:, None])
            st_day = _first_true_day(future_l <= st[:, None])
            ss_day = _first_true_day(future_h >= ss[:, None])

            long_result = np.where(lt_day < ls_day, 1.0, np.where(ls_day < lt_day, -1.0, 0.0))
            short_result = np.where(st_day < ss_day, 1.0, np.where(ss_day < st_day, -1.0, 0.0))
            long_days = np.minimum(np.minimum(lt_day, ls_day), float(horizon))
            short_days = np.minimum(np.minimum(st_day, ss_day), float(horizon))

            # Equal finite first-hit days are same-bar ambiguities; neither wins nor losses.
            long_ambiguous = np.isfinite(lt_day) & np.isfinite(ls_day) & (lt_day == ls_day)
            short_ambiguous = np.isfinite(st_day) & np.isfinite(ss_day) & (st_day == ss_day)
            long_result[long_ambiguous] = np.nan
            short_result[short_ambiguous] = np.nan
            long_result[~valid_entry] = np.nan
            short_result[~valid_entry] = np.nan
            long_days[~valid_entry] = np.nan
            short_days[~valid_entry] = np.nan

            derived[f"long_barrier_{tag}"] = long_result
            derived[f"short_barrier_{tag}"] = short_result
            derived[f"long_days_{tag}"] = long_days
            derived[f"short_days_{tag}"] = short_days
    if derived:
        block = pd.DataFrame(derived, index=out.index)
        out = pd.concat([out, block], axis=1)
    return out.copy()


def _weekly_anchor(df: pd.DataFrame) -> pd.DataFrame:
    # Last available session of each ISO week; all features are computed before filtering.
    iso = df["as_of"].dt.isocalendar()
    key = iso["year"].astype(str) + "-" + iso["week"].astype(str)
    return df.loc[df.groupby(key, sort=False)["as_of"].idxmax()].copy()


def process_symbol_file(args: tuple[str, str, tuple[int, ...], tuple[tuple[float, float], ...], str, int]) -> tuple[str, pd.DataFrame | None, str | None]:
    raw_path, dev_end, horizons, geometries, cadence, min_history = args
    path = Path(raw_path)
    symbol = _safe_symbol_from_filename(path)
    try:
        df = read_daily_file(path, dev_end)
        if len(df) < min_history + max(horizons):
            return symbol, None, "INSUFFICIENT_HISTORY"
        df = engineer_ohlcv_features(df)
        df = add_forward_outcomes(df, horizons, geometries).copy()
        df["symbol"] = symbol
        df["calendar_year"] = df["as_of"].dt.year
        df["month"] = df["as_of"].dt.month
        df["weekday"] = df["as_of"].dt.weekday
        if cadence == "weekly":
            df = _weekly_anchor(df)
        return symbol, df, None
    except Exception as exc:
        return symbol, None, f"{type(exc).__name__}: {exc}"


def iter_jsonl_gz(path: Path) -> Iterable[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def load_certified_pit_feature_matrix(feature_root: Path, dev_end: str) -> pd.DataFrame:
    if not feature_root.exists():
        raise EdgeLabError(f"certified PIT feature root missing: {feature_root}")
    rows: list[dict[str, Any]] = []
    for path in sorted(feature_root.glob("*.jsonl.gz")):
        for rec in iter_jsonl_gz(path):
            as_of = str(rec.get("as_of") or "")[:10]
            if not as_of or as_of > dev_end:
                continue
            vals = rec.get("feature_values") or {}
            row: dict[str, Any] = {"symbol": rec.get("symbol"), "as_of": as_of}
            for fid, val in vals.items():
                if isinstance(val, dict):
                    for k, x in val.items():
                        if isinstance(x, (bool, int, float, str)) or x is None:
                            row[f"pit_{fid}__{k}"] = x
                elif isinstance(val, (bool, int, float, str)) or val is None:
                    row[f"pit_{fid}"] = val
            rows.append(row)
    if not rows:
        raise EdgeLabError("certified PIT feature matrix contained no Development rows")
    out = pd.DataFrame(rows)
    out["as_of"] = pd.to_datetime(out["as_of"])
    return out.drop_duplicates(["symbol", "as_of"], keep="last")


def sanitize_nonfinite_numeric(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Replace +/-inf with NaN across numeric research columns and report counts.

    Infinite values are never legitimate feature thresholds.  Keeping them can
    corrupt qcut/quantile interpolation and downstream model preprocessing.
    """
    out = frame.copy()
    counts: dict[str, int] = {}
    numeric = out.select_dtypes(include=[np.number]).columns
    for c in numeric:
        values = out[c].to_numpy(dtype=float, copy=False)
        bad = np.isinf(values)
        n = int(bad.sum())
        if n:
            counts[str(c)] = n
            out.loc[bad, c] = np.nan
    return out, counts


def add_cross_sectional_ranks(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    candidates = [
        "px_ret_5", "px_ret_20", "px_ret_60", "px_ret_126", "px_ret_252",
        "rsi_14", "atr_pct_14", "rv_20", "rv_60", "volume_ratio_20",
        "dist_sma_20", "dist_sma_60", "drawdown_252", "mom_accel_5_20",
    ]
    for c in candidates:
        if c in out.columns:
            out[f"xrank_{c}"] = out.groupby("as_of", observed=True)[c].rank(pct=True, method="average")
    return out


def chronological_partitions(panel: pd.DataFrame) -> pd.Series:
    dates = np.array(sorted(panel["as_of"].dropna().unique()))
    if len(dates) < 12:
        raise EdgeLabError("not enough distinct dates for discovery/confirmation/internal-holdout partitions")
    i1 = max(1, int(len(dates) * 0.60))
    i2 = max(i1 + 1, int(len(dates) * 0.80))
    d1 = pd.Timestamp(dates[min(i1, len(dates) - 2)])
    d2 = pd.Timestamp(dates[min(i2, len(dates) - 1)])
    p = pd.Series(index=panel.index, dtype="object")
    p.loc[panel["as_of"] < d1] = "DISCOVERY"
    p.loc[(panel["as_of"] >= d1) & (panel["as_of"] < d2)] = "CONFIRMATION"
    p.loc[panel["as_of"] >= d2] = "INTERNAL_HOLDOUT"
    return p


def _numeric_feature_columns(panel: pd.DataFrame) -> list[str]:
    blocked_prefixes = ("fwd_", "mfe_", "mae_", "long_barrier_", "short_barrier_", "long_days_", "short_days_")
    blocked_exact = {"open", "high", "low", "close", "volume", "atr_14", "calendar_year", "month", "weekday"}
    cols = []
    for c in panel.columns:
        if c in blocked_exact or c in {"symbol", "as_of", "partition"} or c.startswith(blocked_prefixes):
            continue
        if pd.api.types.is_numeric_dtype(panel[c]) and panel[c].notna().sum() >= 500:
            cols.append(c)
    return sorted(cols)


def _categorical_feature_columns(panel: pd.DataFrame) -> list[str]:
    cols = []
    for c in panel.columns:
        if not c.startswith("pit_"):
            continue
        if pd.api.types.is_object_dtype(panel[c]) or pd.api.types.is_bool_dtype(panel[c]):
            nunique = panel[c].nunique(dropna=True)
            if 1 < nunique <= 30:
                cols.append(c)
    return sorted(cols)


def _condition_metrics(frame: pd.DataFrame, outcome_col: str, mask: pd.Series, direction: str) -> dict[str, Any] | None:
    base = frame[outcome_col].dropna()
    y = frame.loc[mask, outcome_col].dropna()
    if len(y) == 0 or len(base) == 0:
        return None
    sign = 1.0 if direction == "LONG" else -1.0
    ys = y * sign
    bs = base * sign
    wins = ys > 0
    bwins = bs > 0
    p = float(wins.mean())
    bp = float(bwins.mean())
    edge = p - bp
    mean_ret = float(ys.mean())
    baseline_mean = float(bs.mean())
    mean_edge = mean_ret - baseline_mean
    se = math.sqrt(max(bp * (1 - bp), 1e-12) / max(len(y), 1))
    z = edge / se if se > 0 else 0.0
    pval = float(2 * stats.norm.sf(abs(z)))
    syms = frame.loc[y.index, "symbol"].nunique() if "symbol" in frame.columns else 0
    dates = frame.loc[y.index, "as_of"]
    return {
        "n": int(len(y)), "symbol_count": int(syms), "win_rate": p, "baseline_win_rate": bp,
        "win_rate_edge": edge, "mean_return": mean_ret, "baseline_mean_return": baseline_mean,
        "mean_return_edge": mean_edge, "median_return": float(ys.median()), "p_value": pval,
        "first_date": dates.min().date().isoformat() if len(dates) else None,
        "last_date": dates.max().date().isoformat() if len(dates) else None,
    }


def _bootstrap_ci(values: np.ndarray, seed: int, samples: int) -> tuple[float, float]:
    values = values[np.isfinite(values)]
    if len(values) < 30 or samples <= 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = np.empty(samples)
    for i in range(samples):
        means[i] = rng.choice(values, size=len(values), replace=True).mean()
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def _bh_qvalues(pvalues: Sequence[float]) -> np.ndarray:
    p = np.asarray(pvalues, dtype=float)
    n = len(p)
    if n == 0:
        return p
    order = np.argsort(p)
    ranked = p[order]
    q = ranked * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(q, 0, 1)
    return out


def discover_univariate(panel: pd.DataFrame, horizon: int, min_samples: int) -> pd.DataFrame:
    train = panel[panel["partition"] == "DISCOVERY"].copy()
    outcome = f"fwd_ret_{horizon}"
    rows: list[dict[str, Any]] = []
    for feature in _numeric_feature_columns(train):
        x = train[feature]
        valid = x.notna() & np.isfinite(pd.to_numeric(x, errors="coerce")) & train[outcome].notna() & np.isfinite(pd.to_numeric(train[outcome], errors="coerce"))
        if valid.sum() < min_samples * 4:
            continue
        try:
            q = pd.qcut(x[valid], q=10, duplicates="drop", labels=False)
        except ValueError:
            continue
        for bucket in sorted(pd.unique(q.dropna())):
            mask = pd.Series(False, index=train.index)
            idx = q.index[q == bucket]
            mask.loc[idx] = True
            lo = float(x.loc[idx].min()); hi = float(x.loc[idx].max())
            for direction in ("LONG", "SHORT"):
                m = _condition_metrics(train, outcome, mask, direction)
                if not m or m["n"] < min_samples:
                    continue
                rows.append({
                    "candidate_type": "NUMERIC_DECILE", "feature": feature, "operator": "RANGE",
                    "lower": lo, "upper": hi, "value": None, "direction": direction, "horizon": horizon,
                    **m,
                })
    for feature in _categorical_feature_columns(train):
        for value, count in train[feature].value_counts(dropna=True).items():
            if count < min_samples:
                continue
            mask = train[feature] == value
            for direction in ("LONG", "SHORT"):
                m = _condition_metrics(train, outcome, mask, direction)
                if not m or m["n"] < min_samples:
                    continue
                rows.append({
                    "candidate_type": "CATEGORICAL_STATE", "feature": feature, "operator": "EQ",
                    "lower": None, "upper": None, "value": str(value), "direction": direction, "horizon": horizon,
                    **m,
                })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["q_value"] = _bh_qvalues(out["p_value"].fillna(1.0).to_numpy())
    out["discovery_score"] = (
        out["win_rate_edge"].abs() * np.sqrt(out["n"]) +
        out["mean_return_edge"].abs() * 100.0 * np.sqrt(out["n"])
    )
    return out.sort_values(["q_value", "discovery_score"], ascending=[True, False]).reset_index(drop=True)


def _candidate_mask(frame: pd.DataFrame, rec: pd.Series) -> pd.Series:
    f = rec["feature"]
    if rec["operator"] == "RANGE":
        return frame[f].between(float(rec["lower"]), float(rec["upper"]), inclusive="both")
    return frame[f].astype(str) == str(rec["value"])


def validate_candidates(panel: pd.DataFrame, candidates: pd.DataFrame, min_samples: int) -> pd.DataFrame:
    if candidates.empty:
        return candidates.copy()
    rows = []
    for _, rec in candidates.iterrows():
        out = rec.to_dict()
        for part in ("CONFIRMATION", "INTERNAL_HOLDOUT"):
            frame = panel[panel["partition"] == part]
            mask = _candidate_mask(frame, rec)
            m = _condition_metrics(frame, f"fwd_ret_{int(rec['horizon'])}", mask, str(rec["direction"]))
            prefix = "confirm" if part == "CONFIRMATION" else "holdout"
            if not m:
                out[f"{prefix}_n"] = 0
                continue
            for k, v in m.items():
                out[f"{prefix}_{k}"] = v
        rows.append(out)
    result = pd.DataFrame(rows)
    for prefix in ("confirm", "holdout"):
        result[f"{prefix}_pass"] = (
            (result.get(f"{prefix}_n", 0).fillna(0) >= min_samples) &
            (result.get(f"{prefix}_win_rate_edge", 0).fillna(0) > 0) &
            (result.get(f"{prefix}_mean_return_edge", 0).fillna(0) > 0)
        )
    result["robust_pass"] = result["confirm_pass"] & result["holdout_pass"]
    return result


def discover_interactions(panel: pd.DataFrame, validated_uni: pd.DataFrame, cfg: LabConfig) -> pd.DataFrame:
    good = validated_uni[validated_uni["confirm_pass"]].copy()
    if good.empty:
        return pd.DataFrame()
    good = good.sort_values(["q_value", "discovery_score"], ascending=[True, False])
    unique_features: list[str] = []
    representative: dict[str, pd.Series] = {}
    for _, r in good.iterrows():
        f = str(r["feature"])
        if f not in representative:
            representative[f] = r
            unique_features.append(f)
        if len(unique_features) >= cfg.top_interaction_features:
            break
    train = panel[panel["partition"] == "DISCOVERY"]
    rows = []
    count = 0
    for i, f1 in enumerate(unique_features):
        for f2 in unique_features[i + 1 :]:
            if count >= cfg.max_pair_candidates:
                break
            r1, r2 = representative[f1], representative[f2]
            if int(r1["horizon"]) != int(r2["horizon"]) or r1["direction"] != r2["direction"]:
                continue
            mask = _candidate_mask(train, r1) & _candidate_mask(train, r2)
            m = _condition_metrics(train, f"fwd_ret_{int(r1['horizon'])}", mask, str(r1["direction"]))
            count += 1
            if not m or m["n"] < cfg.min_samples:
                continue
            rows.append({
                "candidate_type": "PAIR_INTERACTION", "feature": f"{f1} & {f2}", "operator": "AND",
                "component_1": json.dumps(r1.to_dict(), default=_json_default),
                "component_2": json.dumps(r2.to_dict(), default=_json_default),
                "direction": r1["direction"], "horizon": int(r1["horizon"]), **m,
            })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["q_value"] = _bh_qvalues(out["p_value"].fillna(1.0))
    out["discovery_score"] = out["win_rate_edge"].abs() * np.sqrt(out["n"])
    return out.sort_values(["q_value", "discovery_score"], ascending=[True, False]).reset_index(drop=True)


def _interaction_mask(frame: pd.DataFrame, rec: pd.Series) -> pd.Series:
    r1 = pd.Series(json.loads(rec["component_1"]))
    r2 = pd.Series(json.loads(rec["component_2"]))
    return _candidate_mask(frame, r1) & _candidate_mask(frame, r2)


def validate_interactions(panel: pd.DataFrame, interactions: pd.DataFrame, min_samples: int) -> pd.DataFrame:
    rows = []
    for _, rec in interactions.iterrows():
        out = rec.to_dict()
        for part, prefix in (("CONFIRMATION", "confirm"), ("INTERNAL_HOLDOUT", "holdout")):
            frame = panel[panel["partition"] == part]
            m = _condition_metrics(frame, f"fwd_ret_{int(rec['horizon'])}", _interaction_mask(frame, rec), str(rec["direction"]))
            if not m:
                out[f"{prefix}_n"] = 0
            else:
                for k, v in m.items(): out[f"{prefix}_{k}"] = v
        rows.append(out)
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    for prefix in ("confirm", "holdout"):
        result[f"{prefix}_pass"] = (
            (result.get(f"{prefix}_n", 0).fillna(0) >= min_samples) &
            (result.get(f"{prefix}_win_rate_edge", 0).fillna(0) > 0) &
            (result.get(f"{prefix}_mean_return_edge", 0).fillna(0) > 0)
        )
    result["robust_pass"] = result["confirm_pass"] & result["holdout_pass"]
    return result



def candidate_key(rec: pd.Series | dict[str, Any]) -> str:
    get = rec.get
    def norm(v):
        try:
            if pd.isna(v): return None
        except Exception: pass
        return v
    payload = {"candidate_type": norm(get("candidate_type")), "feature": norm(get("feature")), "operator": norm(get("operator")),
               "lower": norm(get("lower")), "upper": norm(get("upper")), "value": norm(get("value")),
               "direction": str(get("direction")), "horizon": int(get("horizon")),
               "component_1": norm(get("component_1")), "component_2": norm(get("component_2"))}
    raw = json.dumps(payload, sort_keys=True, default=_json_default, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _identity_fields(rec: pd.Series | dict[str, Any]) -> dict[str, Any]:
    return {"candidate_key": candidate_key(rec), "feature": rec.get("feature"), "operator": rec.get("operator"),
            "lower": rec.get("lower"), "upper": rec.get("upper"), "value": rec.get("value"),
            "direction": rec.get("direction"), "horizon": int(rec.get("horizon"))}

def evaluate_barrier_geometry(panel: pd.DataFrame, candidates: pd.DataFrame, cfg: LabConfig) -> pd.DataFrame:
    survivors = candidates[candidates.get("robust_pass", False) == True].head(100) if not candidates.empty else candidates
    rows = []
    if survivors.empty:
        return pd.DataFrame()
    for _, rec in survivors.iterrows():
        for part in ("DISCOVERY", "CONFIRMATION", "INTERNAL_HOLDOUT"):
            frame = panel[panel["partition"] == part]
            mask = _candidate_mask(frame, rec)
            direction = str(rec["direction"]).lower()
            horizon = int(rec["horizon"])
            for target_atr, stop_atr in cfg.target_stop_geometries:
                tag = f"t{str(target_atr).replace('.', 'p')}_s{str(stop_atr).replace('.', 'p')}_h{horizon}"
                col = f"{direction}_barrier_{tag}"
                if col not in frame.columns:
                    continue
                vals = frame.loc[mask, col].dropna()
                resolved = vals[vals != 0]
                if len(vals) < cfg.min_samples:
                    continue
                wins = int((resolved == 1).sum()); losses = int((resolved == -1).sum())
                unresolved = int((vals == 0).sum())
                expectancy_r = (wins * target_atr - losses * stop_atr) / max(wins + losses, 1)
                rows.append({
                    **_identity_fields(rec),
                    "partition": part, "target_atr": target_atr, "stop_atr": stop_atr,
                    "n": len(vals), "wins": wins, "losses": losses, "unresolved": unresolved,
                    "resolved_win_rate": wins / max(wins + losses, 1), "expectancy_r": expectancy_r,
                })
    return pd.DataFrame(rows)


def ml_hypothesis_generation(panel: pd.DataFrame, cfg: LabConfig) -> pd.DataFrame:
    if not cfg.include_ml_hypothesis_generation:
        return pd.DataFrame()
    numeric = _numeric_feature_columns(panel)
    if not numeric:
        return pd.DataFrame()
    rows = []
    for horizon in cfg.horizons:
        outcome = f"fwd_ret_{horizon}"
        train = panel[panel["partition"] == "DISCOVERY"].dropna(subset=[outcome])
        confirm = panel[panel["partition"] == "CONFIRMATION"].dropna(subset=[outcome])
        if len(train) < 2000 or len(confirm) < 500:
            continue
        # Cap width to avoid legacy PIT feature explosion.  Sanitize again at the
        # ML boundary so resumed legacy checkpoints or merge-time coercions can
        # never propagate +/-inf into sklearn.
        availability = []
        sanitized_train: dict[str, pd.Series] = {}
        sanitized_confirm: dict[str, pd.Series] = {}
        for c in numeric:
            tr = pd.to_numeric(train[c], errors="coerce").replace([np.inf, -np.inf], np.nan)
            va = pd.to_numeric(confirm[c], errors="coerce").replace([np.inf, -np.inf], np.nan)
            finite_n = int(tr.notna().sum())
            if finite_n == 0:
                continue
            var = float(tr.var(skipna=True))
            if not np.isfinite(var):
                var = 0.0
            sanitized_train[c] = tr
            sanitized_confirm[c] = va
            availability.append((c, finite_n, var))
        cols = [x[0] for x in sorted(availability, key=lambda x: (x[1], x[2]), reverse=True)[:80]]
        if not cols:
            continue
        Xtr = pd.DataFrame({c: sanitized_train[c] for c in cols}, index=train.index)
        Xva = pd.DataFrame({c: sanitized_confirm[c] for c in cols}, index=confirm.index)
        ytr, yva = (train[outcome] > 0).astype(int), (confirm[outcome] > 0).astype(int)
        models = {
            "LOGISTIC_L2": Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)), ("sc", StandardScaler()), ("m", LogisticRegression(max_iter=500, C=0.5, random_state=cfg.random_seed))]),
            "RANDOM_FOREST": Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=False)), ("m", RandomForestClassifier(n_estimators=250, max_depth=7, min_samples_leaf=100, n_jobs=1, random_state=cfg.random_seed, class_weight="balanced_subsample"))]),
            "HIST_GRADIENT_BOOSTING": Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=False)), ("m", HistGradientBoostingClassifier(max_iter=150, max_leaf_nodes=15, learning_rate=0.05, l2_regularization=1.0, min_samples_leaf=100, random_state=cfg.random_seed))]),
        }
        for name, model in models.items():
            model.fit(Xtr, ytr)
            p = model.predict_proba(Xva)[:, 1]
            pred = (p >= 0.5).astype(int)
            auc = roc_auc_score(yva, p) if yva.nunique() > 1 else float("nan")
            bal = balanced_accuracy_score(yva, pred)
            rows.append({"model": name, "horizon": horizon, "train_n": len(train), "confirmation_n": len(confirm), "confirmation_auc": auc, "confirmation_balanced_accuracy": bal, "feature_count": len(cols)})
            fitted = model.named_steps["m"]
            if hasattr(fitted, "feature_importances_"):
                imp = np.asarray(fitted.feature_importances_)[: len(cols)]
                for rank, idx in enumerate(np.argsort(imp)[::-1][:15], 1):
                    rows.append({"model": name + "_FEATURE_IMPORTANCE", "horizon": horizon, "feature": cols[idx], "rank": rank, "importance": float(imp[idx])})
            elif hasattr(fitted, "coef_"):
                coef = np.asarray(fitted.coef_[0])[: len(cols)]
                for rank, idx in enumerate(np.argsort(np.abs(coef))[::-1][:15], 1):
                    rows.append({"model": name + "_COEFFICIENT", "horizon": horizon, "feature": cols[idx], "rank": rank, "importance": float(abs(coef[idx])), "signed_effect": float(coef[idx])})
    return pd.DataFrame(rows)


def stability_evidence(panel: pd.DataFrame, validated: pd.DataFrame, cfg: LabConfig) -> pd.DataFrame:
    survivors = validated[validated.get("robust_pass", False) == True].head(150) if not validated.empty else validated
    rows = []
    for _, rec in survivors.iterrows():
        outcome = f"fwd_ret_{int(rec['horizon'])}"
        sign = 1.0 if rec["direction"] == "LONG" else -1.0
        for year in sorted(panel["calendar_year"].dropna().unique()):
            frame = panel[panel["calendar_year"] == year]
            mask = _candidate_mask(frame, rec)
            vals = frame.loc[mask, outcome].dropna() * sign
            if len(vals) < max(30, cfg.min_samples // 5):
                continue
            rows.append({
                **_identity_fields(rec),
                "year": int(year), "n": len(vals), "win_rate": float((vals > 0).mean()), "mean_return": float(vals.mean())
            })
    return pd.DataFrame(rows)



def robustness_destruction_tests(panel: pd.DataFrame, validated: pd.DataFrame, cfg: LabConfig) -> pd.DataFrame:
    """Try to falsify internally robust candidates with timing/threshold/symbol tests."""
    if validated.empty or "robust_pass" not in validated.columns:
        return pd.DataFrame()
    survivors = validated[validated["robust_pass"] == True].head(150)
    rows: list[dict[str, Any]] = []
    holdout = panel[panel["partition"] == "INTERNAL_HOLDOUT"]
    for _, rec in survivors.iterrows():
        horizon = int(rec["horizon"]); direction = str(rec["direction"])
        base_mask = _candidate_mask(holdout, rec)
        delay_col = f"fwd_ret_{horizon}_delay1"
        delayed = _condition_metrics(holdout, delay_col, base_mask, direction) if delay_col in holdout else None
        sign = 1.0 if direction == "LONG" else -1.0
        selected = holdout.loc[base_mask, ["symbol", f"fwd_ret_{horizon}"]].dropna()
        symbol_means = selected.assign(signed=selected[f"fwd_ret_{horizon}"] * sign).groupby("symbol")["signed"].agg(["count", "mean"])
        symbol_means = symbol_means[symbol_means["count"] >= 5]
        symbol_positive_fraction = float((symbol_means["mean"] > 0).mean()) if len(symbol_means) else float("nan")
        perturb_pass = True
        perturb_results = []
        if rec["operator"] == "RANGE" and pd.notna(rec.get("lower")) and pd.notna(rec.get("upper")):
            lo, hi = float(rec["lower"]), float(rec["upper"])
            center, half = (lo + hi) / 2.0, max((hi - lo) / 2.0, 1e-12)
            for label, factor in (("NARROW_10PCT", 0.9), ("WIDE_10PCT", 1.1), ("WIDE_25PCT", 1.25)):
                plo, phi = center - half * factor, center + half * factor
                mask = holdout[str(rec["feature"])].between(plo, phi, inclusive="both")
                m = _condition_metrics(holdout, f"fwd_ret_{horizon}", mask, direction)
                passed = bool(m and m["n"] >= max(50, cfg.min_samples // 2) and m["win_rate_edge"] > 0 and m["mean_return_edge"] > 0)
                perturb_pass = perturb_pass and passed
                perturb_results.append({"label": label, "lower": plo, "upper": phi, "pass": passed, "metrics": m})
        delayed_pass = bool(delayed and delayed["n"] >= max(50, cfg.min_samples // 2) and delayed["win_rate_edge"] > 0 and delayed["mean_return_edge"] > 0)
        base_mean = float(rec.get("holdout_mean_return", float("nan")))
        rows.append({
            **_identity_fields(rec),
            "delayed_entry_pass": delayed_pass,
            "delayed_entry_n": delayed.get("n") if delayed else 0,
            "delayed_entry_win_rate_edge": delayed.get("win_rate_edge") if delayed else np.nan,
            "delayed_entry_mean_return_edge": delayed.get("mean_return_edge") if delayed else np.nan,
            "threshold_perturbation_pass": bool(perturb_pass),
            "threshold_perturbations_json": json.dumps(perturb_results, default=_json_default),
            "symbol_robust_count": int(len(symbol_means)),
            "symbol_positive_mean_fraction": symbol_positive_fraction,
            "net_mean_return_after_10bps": base_mean - 0.001 if np.isfinite(base_mean) else np.nan,
            "net_mean_return_after_25bps": base_mean - 0.0025 if np.isfinite(base_mean) else np.nan,
            "net_mean_return_after_50bps": base_mean - 0.005 if np.isfinite(base_mean) else np.nan,
            "destruction_pass": bool(delayed_pass and perturb_pass and (not np.isfinite(symbol_positive_fraction) or symbol_positive_fraction >= 0.55)),
        })
    return pd.DataFrame(rows)


def stationarity_confounder_tests(panel: pd.DataFrame, validated: pd.DataFrame, cfg: LabConfig) -> pd.DataFrame:
    if validated.empty or "robust_pass" not in validated.columns: return pd.DataFrame()
    holdout = panel[panel["partition"] == "INTERNAL_HOLDOUT"].copy(); rows=[]
    for _, rec in validated[validated["robust_pass"] == True].head(150).iterrows():
        h=int(rec["horizon"]); direction=str(rec["direction"]); outcome=f"fwd_ret_{h}"; sign=1.0 if direction=="LONG" else -1.0
        sel=holdout.loc[_candidate_mask(holdout,rec), ["symbol","as_of","close",outcome]].dropna(subset=[outcome]).copy()
        bs=sel.assign(signed=sel[outcome]*sign).groupby("symbol")["signed"].agg(["count","sum","mean"]).sort_values("sum",ascending=False)
        total=float((sel[outcome]*sign).sum()) if len(sel) else np.nan
        top5=float(bs.head(5)["sum"].sum()/total) if np.isfinite(total) and abs(total)>1e-12 else np.nan
        no10=sel[~sel["symbol"].isin(set(bs.head(10).index))]; no10mean=float((no10[outcome]*sign).mean()) if len(no10) else np.nan
        floors={}
        for floor in (5.,10.,20.):
            sub=sel[sel["close"]>=floor]; vals=sub[outcome]*sign
            floors[str(int(floor))]={"n":int(len(sub)),"mean_return":float(vals.mean()) if len(vals) else np.nan,"win_rate":float((vals>0).mean()) if len(vals) else np.nan}
        eras={}
        for label,lo,hi in (("2003_2007",2003,2007),("2008_2012",2008,2012),("2013_2017",2013,2017)):
            sub=sel[sel["as_of"].dt.year.between(lo,hi)]; vals=sub[outcome]*sign
            eras[label]={"n":int(len(sub)),"mean_return":float(vals.mean()) if len(vals) else np.nan,"win_rate":float((vals>0).mean()) if len(vals) else np.nan}
        poseras=sum(1 for v in eras.values() if v["n"]>=max(30,cfg.min_samples//5) and np.isfinite(v["mean_return"]) and v["mean_return"]>0)
        posfrac=float((bs["mean"]>0).mean()) if len(bs) else np.nan
        passed=bool(len(sel)>=cfg.min_samples and len(bs)>=20 and posfrac>=0.55 and poseras>=2 and (not np.isfinite(no10mean) or no10mean>0))
        rows.append({**_identity_fields(rec),"base_n":int(len(sel)),"unique_symbols":int(len(bs)),"equal_symbol_mean_return":float(bs["mean"].mean()) if len(bs) else np.nan,"positive_symbol_fraction":posfrac,"top5_profit_contribution_share":top5,"mean_return_without_top10_symbols":no10mean,"price_floor_json":json.dumps(floors,default=_json_default),"era_stability_json":json.dumps(eras,default=_json_default),"positive_eras":poseras,"stationarity_confounder_pass":passed})
    return pd.DataFrame(rows)


def ml_tail_evidence(panel: pd.DataFrame, cfg: LabConfig) -> pd.DataFrame:
    if not cfg.include_ml_hypothesis_generation: return pd.DataFrame()
    numeric=_numeric_feature_columns(panel); rows=[]
    for h in [x for x in cfg.horizons if x>=15]:
        outcome=f"fwd_ret_{h}"; tr=panel[panel["partition"]=="DISCOVERY"].dropna(subset=[outcome]); va=panel[panel["partition"]=="CONFIRMATION"].dropna(subset=[outcome])
        if len(tr)<2000 or len(va)<500: continue
        av=[]
        for c in numeric:
            x=pd.to_numeric(tr[c],errors="coerce").replace([np.inf,-np.inf],np.nan)
            if x.notna().sum():
                v=float(x.var(skipna=True)); av.append((c,int(x.notna().sum()),0. if not np.isfinite(v) else v))
        cols=[x[0] for x in sorted(av,key=lambda z:(z[1],z[2]),reverse=True)[:80]]
        Xtr=tr[cols].apply(pd.to_numeric,errors="coerce").replace([np.inf,-np.inf],np.nan); Xva=va[cols].apply(pd.to_numeric,errors="coerce").replace([np.inf,-np.inf],np.nan)
        model=Pipeline([("imp",SimpleImputer(strategy="median")),("m",HistGradientBoostingClassifier(max_iter=150,max_leaf_nodes=15,learning_rate=.05,l2_regularization=1.,min_samples_leaf=100,random_state=cfg.random_seed))]); model.fit(Xtr,(tr[outcome]>0).astype(int)); p=model.predict_proba(Xva)[:,1]; raw=va[outcome].to_numpy(); order=np.argsort(p)
        for frac in (.01,.025,.05,.10,.20):
            k=max(1,int(len(va)*frac))
            for direction,idxs in (("LONG",order[-k:]),("SHORT",order[:k])):
                sign=1 if direction=="LONG" else -1; vals=raw[idxs]*sign; base=raw*sign
                rows.append({"model":"HIST_GRADIENT_BOOSTING","horizon":h,"tail_fraction":frac,"direction":direction,"n":k,"unique_symbols":int(va.iloc[idxs]["symbol"].nunique()),"win_rate":float((vals>0).mean()),"mean_return":float(vals.mean()),"median_return":float(np.median(vals)),"baseline_win_rate":float((base>0).mean()),"baseline_mean_return":float(base.mean())})
    out=pd.DataFrame(rows)
    if not out.empty: out["win_rate_edge"]=out["win_rate"]-out["baseline_win_rate"]; out["mean_return_edge"]=out["mean_return"]-out["baseline_mean_return"]
    return out

def build_edge_registry(validated: pd.DataFrame, interactions: pd.DataFrame, barrier: pd.DataFrame, stability: pd.DataFrame, robustness: pd.DataFrame, cfg: LabConfig) -> pd.DataFrame:
    sources = []
    if not validated.empty:
        v = validated[validated.get("robust_pass", False) == True].copy()
        v["source"] = "UNIVARIATE"
        sources.append(v)
    if not interactions.empty:
        i = interactions[interactions.get("robust_pass", False) == True].copy()
        i["source"] = "PAIR_INTERACTION"
        sources.append(i)
    if not sources:
        return pd.DataFrame()
    reg = pd.concat(sources, ignore_index=True, sort=False)
    if reg.empty:
        return pd.DataFrame()
    reg["candidate_key"] = reg.apply(candidate_key, axis=1)
    reg["edge_id"] = [f"M77E-{i+1:05d}" for i in range(len(reg))]
    reg["status"] = "ROBUST_INTERNAL_CANDIDATE"
    reg["production_authority_effect"] = False
    reg["validation_partition_opened"] = False
    reg["final_holdout_opened"] = False
    reg["eligible_for_production"] = False
    reg["requires_external_validation"] = True
    if not stability.empty:
        year_stats = stability.groupby(["candidate_key"], dropna=False).agg(
            stable_years=("year", "nunique"), positive_mean_years=("mean_return", lambda x: int((x > 0).sum())),
            positive_win_years=("win_rate", lambda x: int((x > 0.5).sum())), min_year_n=("n", "min")
        ).reset_index()
        reg = reg.merge(year_stats, on=["candidate_key"], how="left")
    if not robustness.empty:
        reg = reg.merge(robustness.drop(columns=[c for c in ["feature","operator","lower","upper","value","direction","horizon"] if c in robustness.columns]), on=["candidate_key"], how="left")
        reg.loc[reg["destruction_pass"] == False, "status"] = "ROBUST_INTERNAL_CANDIDATE_FAILED_DESTRUCTION_TEST"
    if not barrier.empty:
        bh = barrier[barrier["partition"] == "INTERNAL_HOLDOUT"].copy()
        if not bh.empty:
            best = bh.sort_values("expectancy_r", ascending=False).drop_duplicates(["candidate_key"])
            best = best[["candidate_key", "target_atr", "stop_atr", "resolved_win_rate", "expectancy_r"]].rename(columns={
                "target_atr": "best_holdout_target_atr", "stop_atr": "best_holdout_stop_atr",
                "resolved_win_rate": "best_holdout_barrier_win_rate", "expectancy_r": "best_holdout_expectancy_r",
            })
            reg = reg.merge(best, on=["candidate_key"], how="left")
    sort_cols = [c for c in ["holdout_mean_return_edge", "holdout_win_rate_edge", "confirm_mean_return_edge"] if c in reg.columns]
    if sort_cols:
        reg = reg.sort_values(sort_cols, ascending=False)
    return reg.reset_index(drop=True)


def write_readable_report(path: Path, summary: dict[str, Any], registry: pd.DataFrame) -> None:
    lines = [
        "# M77.21.0 Edge Discovery Laboratory — Run Report", "",
        f"- Version: `{VERSION}`",
        f"- Status: **{summary['status']}**",
        f"- Development boundary: `{summary['development_boundary']}`",
        f"- Validation partition opened: **NO**",
        f"- Final holdout opened: **NO**",
        f"- Production authority effect: **NONE**",
        f"- Symbols processed: {summary['symbols_processed']}",
        f"- Research rows: {summary['panel_rows']}",
        f"- Numeric features searched: {summary['numeric_feature_count']}",
        f"- Univariate hypotheses tested: {summary['univariate_hypotheses_tested']}",
        f"- Pair interactions tested/materialized: {summary['pair_interactions_tested']}",
        f"- Robust internal candidates: {summary['robust_internal_candidates']}",
        f"- Candidates surviving destruction tests: {summary.get('destruction_test_survivors', 0)}", "",
        "## Governance", "",
        "This laboratory is discovery-only. A robust internal candidate is not a production edge and cannot alter Stock Intelligence, Decision Intelligence, options selection, execution, portfolio, or management authority.", "",
        "## Top internal candidates", "",
    ]
    if registry.empty:
        lines.append("No candidate survived both confirmation and internal holdout gates.")
    else:
        display_registry = registry[(registry.get("destruction_pass", False) == True)] if "destruction_pass" in registry.columns else registry
        if display_registry.empty:
            lines.append("Candidates survived chronological confirmation/internal holdout, but none passed the additional destruction tests yet.")
        for _, r in display_registry.head(25).iterrows():
            lines.append(
                f"- **{r.get('edge_id')}** {r.get('direction')} H{int(r.get('horizon'))} `{r.get('feature')}` — "
                f"holdout win-rate edge={float(r.get('holdout_win_rate_edge', float('nan'))):+.2%}, "
                f"holdout mean-return edge={float(r.get('holdout_mean_return_edge', float('nan'))):+.3%}, "
                f"n={int(r.get('holdout_n', 0) or 0)}"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_lab(config: LabConfig) -> dict[str, Any]:
    config.validate(); _assert_research_only_paths(config)
    root = Path(config.project_root).resolve()
    daily_root = _resolve(root, config.daily_root); feature_root = _resolve(root, config.feature_root)
    outroot = _resolve(root, config.output_root)
    assert daily_root is not None and outroot is not None
    outroot.mkdir(parents=True, exist_ok=True)
    checkpoints = outroot / "checkpoints"; checkpoints.mkdir(exist_ok=True)
    manifest_path = outroot / "run_manifest.json"
    fingerprint = hashlib.sha256(json.dumps(asdict(config), sort_keys=True, default=_json_default).encode()).hexdigest()
    manifest = {
        "version": VERSION, "status": "RUNNING", "started_at": datetime.now(timezone.utc).isoformat(),
        "config": asdict(config), "config_sha256": fingerprint,
        "governance": {
            "development_only": True, "development_end": config.dev_end, "validation_partition_opened": False,
            "final_holdout_opened": False, "production_authority_effect": False, "database_access": "NONE",
            "polygon_api_called": False, "production_files_modified": False,
        }, "completed_stages": []
    }
    _atomic_json(manifest_path, manifest)

    panel_cache = checkpoints / "panel.pkl.gz"
    if config.resume and panel_cache.exists():
        panel = pd.read_pickle(panel_cache, compression="gzip")
        panel, nonfinite_counts = sanitize_nonfinite_numeric(panel)
        _atomic_json(outroot / "nonfinite_sanitization.json", {"columns": nonfinite_counts, "total_replaced": int(sum(nonfinite_counts.values())), "source": "RESUMED_PANEL"})
        manifest["completed_stages"].append("PANEL_RESUMED")
    else:
        files = discover_daily_files(daily_root)
        tasks = [(str(p), config.dev_end, tuple(config.horizons), tuple(config.target_stop_geometries), config.cadence, config.min_history) for p in files]
        frames = []; failures = []
        if config.workers == 1:
            results = map(process_symbol_file, tasks)
            for symbol, frame, err in results:
                if frame is not None: frames.append(frame)
                else: failures.append({"symbol": symbol, "reason": err})
        else:
            with ProcessPoolExecutor(max_workers=config.workers) as ex:
                futs = {ex.submit(process_symbol_file, t): t[0] for t in tasks}
                for fut in as_completed(futs):
                    symbol, frame, err = fut.result()
                    if frame is not None: frames.append(frame)
                    else: failures.append({"symbol": symbol, "reason": err})
        if not frames:
            raise EdgeLabError("no symbol histories were eligible")
        panel = pd.concat(frames, ignore_index=True, sort=False)
        if config.include_certified_pit_features and feature_root is not None and feature_root.exists():
            pit = load_certified_pit_feature_matrix(feature_root, config.dev_end)
            panel = panel.merge(pit, on=["symbol", "as_of"], how="left", validate="many_to_one")
        panel, nonfinite_counts = sanitize_nonfinite_numeric(panel)
        _atomic_json(outroot / "nonfinite_sanitization.json", {"columns": nonfinite_counts, "total_replaced": int(sum(nonfinite_counts.values()))})
        panel = add_cross_sectional_ranks(panel)
        panel["partition"] = chronological_partitions(panel)
        panel = panel.sort_values(["as_of", "symbol"]).reset_index(drop=True)
        panel.to_pickle(panel_cache, compression="gzip", protocol=5)
        _atomic_csv(outroot / "symbol_failures.csv", pd.DataFrame(failures, columns=["symbol", "reason"]))
        manifest["completed_stages"].append("PANEL_BUILT")
        _atomic_json(manifest_path, manifest)

    numeric_count = len(_numeric_feature_columns(panel))
    uni_parts = []
    for h in config.horizons:
        p = checkpoints / f"univariate_h{h}.csv"
        if config.resume and p.exists():
            u = pd.read_csv(p)
        else:
            u = discover_univariate(panel, h, config.min_samples)
            _atomic_csv(p, u)
        if not u.empty:
            uni_parts.append(u)
    univariate = pd.concat(uni_parts, ignore_index=True, sort=False) if uni_parts else pd.DataFrame()
    _atomic_csv(outroot / "univariate_discovery.csv", univariate)
    manifest["completed_stages"].append("UNIVARIATE_DISCOVERY")
    _atomic_json(manifest_path, manifest)

    top = univariate.sort_values(["q_value", "discovery_score"], ascending=[True, False]).head(config.top_univariate * len(config.horizons)) if not univariate.empty else univariate
    validated = validate_candidates(panel, top, config.min_samples)
    _atomic_csv(outroot / "univariate_validated.csv", validated)
    manifest["completed_stages"].append("UNIVARIATE_CONFIRMATION_INTERNAL_HOLDOUT")
    _atomic_json(manifest_path, manifest)

    interactions = discover_interactions(panel, validated, config)
    interactions = validate_interactions(panel, interactions, config.min_samples)
    _atomic_csv(outroot / "pair_interactions_validated.csv", interactions)
    manifest["completed_stages"].append("PAIR_INTERACTIONS")
    _atomic_json(manifest_path, manifest)

    barrier = evaluate_barrier_geometry(panel, validated, config)
    _atomic_csv(outroot / "barrier_geometry_evidence.csv", barrier)
    stability = stability_evidence(panel, validated, config)
    _atomic_csv(outroot / "year_stability_evidence.csv", stability)
    robustness = robustness_destruction_tests(panel, validated, config)
    _atomic_csv(outroot / "robustness_destruction_evidence.csv", robustness)
    stationarity = stationarity_confounder_tests(panel, validated, config)
    _atomic_csv(outroot / "stationarity_confounder_evidence.csv", stationarity)
    manifest["completed_stages"].append("PATH_STABILITY_DESTRUCTION_AND_STATIONARITY_TESTS")
    _atomic_json(manifest_path, manifest)

    ml = ml_hypothesis_generation(panel, config)
    _atomic_csv(outroot / "ml_hypothesis_evidence.csv", ml)
    ml_tail = ml_tail_evidence(panel, config)
    _atomic_csv(outroot / "ml_tail_evidence.csv", ml_tail)
    manifest["completed_stages"].append("ML_HYPOTHESIS_GENERATION")

    registry = build_edge_registry(validated, interactions, barrier, stability, robustness, config)
    if not registry.empty and not stationarity.empty:
        st=stationarity.drop(columns=[c for c in ["feature","operator","lower","upper","value","direction","horizon"] if c in stationarity.columns])
        registry=registry.merge(st,on="candidate_key",how="left")
        registry.loc[registry["stationarity_confounder_pass"] == False,"status"]="ROBUST_INTERNAL_CANDIDATE_FAILED_STATIONARITY_CONFOUNDER"
    _atomic_csv(outroot / "edge_registry.csv", registry)
    rejected = validated[validated.get("robust_pass", False) != True].copy() if not validated.empty else pd.DataFrame()
    _atomic_csv(outroot / "rejected_hypotheses.csv", rejected)

    summary = {
        "version": VERSION, "status": "COMPLETE", "development_boundary": config.dev_end,
        "symbols_processed": int(panel["symbol"].nunique()), "panel_rows": int(len(panel)),
        "partition_rows": {str(k): int(v) for k, v in panel["partition"].value_counts().to_dict().items()},
        "numeric_feature_count": numeric_count, "univariate_hypotheses_tested": int(len(univariate)),
        "pair_interactions_tested": int(len(interactions)), "robust_internal_candidates": int(len(registry)),
        "destruction_test_survivors": int((registry.get("destruction_pass", pd.Series(dtype=bool)) == True).sum()) if not registry.empty else 0,
        "stationarity_confounder_survivors": int((registry.get("stationarity_confounder_pass", pd.Series(dtype=bool)) == True).sum()) if not registry.empty else 0,
        "validation_partition_opened": False, "final_holdout_opened": False,
        "production_authority_effect": False, "polygon_api_called": False,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    _atomic_json(outroot / "edge_discovery_summary.json", summary)
    write_readable_report(outroot / "EDGE_DISCOVERY_REPORT.md", summary, registry)
    manifest["status"] = "COMPLETE"; manifest["completed_stages"].append("EDGE_REGISTRY_PUBLISHED_RESEARCH_ONLY")
    manifest["completed_at"] = summary["completed_at"]
    _atomic_json(manifest_path, manifest)
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="M77.21.0 exhaustive Development-only Edge Discovery Laboratory")
    ap.add_argument("--project-root", default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--daily-root", default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--feature-root", default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--output-root", default="research_data/m77_21_0/edge_discovery_lab")
    ap.add_argument("--cadence", choices=["daily", "weekly"], default="weekly")
    ap.add_argument("--dev-end", default=DEFAULT_DEV_END)
    ap.add_argument("--workers", type=int, default=max(1, min(6, (os.cpu_count() or 4) - 1)))
    ap.add_argument("--min-samples", type=int, default=250)
    ap.add_argument("--min-history", type=int, default=300)
    ap.add_argument("--top-univariate", type=int, default=80)
    ap.add_argument("--top-interaction-features", type=int, default=18)
    ap.add_argument("--no-pit-features", action="store_true")
    ap.add_argument("--no-ml", action="store_true")
    ap.add_argument("--no-resume", action="store_true")
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    a = build_arg_parser().parse_args(argv)
    cfg = LabConfig(
        project_root=a.project_root, daily_root=a.daily_root, feature_root=None if a.no_pit_features else a.feature_root,
        output_root=a.output_root, cadence=a.cadence, workers=a.workers, min_samples=a.min_samples,
        min_history=a.min_history, top_univariate=a.top_univariate, top_interaction_features=a.top_interaction_features,
        include_certified_pit_features=not a.no_pit_features, include_ml_hypothesis_generation=not a.no_ml,
        resume=not a.no_resume,
    )
    summary = run_lab(cfg)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0
