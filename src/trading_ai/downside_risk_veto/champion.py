from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from trading_ai.research.m77.edge_discovery_lab import _numeric_feature_columns
from trading_ai.research.m77.multivariate_tail_lab import TailLabConfig, _model, _select_fold_features
from .service import CHAMPION_ID, CERTIFIED_PROTOCOL, DEFAULT_CHAMPION_META

EXPECTED_FINAL_PREREGISTRATION_SHA256 = "6231916aa4f7eba1eb3e038a56bb32ee67aeb84539923dd933bc51e200ac0568"
FINAL_SUMMARY = "research_data/m77_22_4/preregistered_final_holdout_downside_risk_veto/preregistered_final_holdout_summary.json"
DEV_PANEL = "research_data/m77_21_0/edge_discovery_lab/checkpoints/panel.pkl.gz"
MODEL_REL = "data/downside_risk_veto/champion/DRVE-CHAMPION-001.joblib"
META_REL = DEFAULT_CHAMPION_META


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_sha(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent); os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True, default=str); fh.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def materialize_champion(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    summary_path = root / FINAL_SUMMARY
    panel_path = root / DEV_PANEL
    if not summary_path.exists():
        raise RuntimeError(f"M77.22.4 Final Holdout summary missing: {summary_path}")
    if not panel_path.exists():
        raise RuntimeError(f"M77 Development panel missing: {panel_path}")
    final = json.loads(summary_path.read_text())
    if final.get("primary_final_holdout_verdict") != "PASS":
        raise RuntimeError("M77.22.4 Final Holdout certification did not PASS")
    if final.get("preregistration_sha256") != EXPECTED_FINAL_PREREGISTRATION_SHA256:
        raise RuntimeError("M77.22.4 preregistration identity changed")
    if final.get("production_authority_effect") is not False:
        raise RuntimeError("M77.22.4 research authority unexpectedly affected production")

    meta_path = root / META_REL
    model_path = root / MODEL_REL
    if meta_path.exists() and model_path.exists():
        existing = json.loads(meta_path.read_text())
        if existing.get("champion_id") == CHAMPION_ID and existing.get("final_holdout_certified") is True:
            if existing.get("model_file_sha256") == _sha256(model_path):
                return existing
        raise RuntimeError("Existing downside-risk champion artifact is inconsistent; manual governance review required")

    panel = pd.read_pickle(panel_path, compression="gzip")
    panel["as_of"] = pd.to_datetime(panel["as_of"])
    outcome = "fwd_ret_20"
    train = panel.dropna(subset=[outcome]).copy()
    numeric = _numeric_feature_columns(panel)
    cols = _select_fold_features(train, numeric, 80)
    if len(cols) != 80:
        raise RuntimeError(f"Expected frozen top-80 feature set, got {len(cols)}")
    X = train.reindex(columns=cols).apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    y = (pd.to_numeric(train[outcome], errors="coerce") > 0).astype(int)
    cfg = TailLabConfig(project_root=str(root))
    model = _model(cfg)
    model.fit(X, y)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=model_path.name + ".", suffix=".tmp", dir=model_path.parent); os.close(fd)
    try:
        joblib.dump(model, tmp)
        os.replace(tmp, model_path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    model_sha = _sha256(model_path)
    feature_sha = _canonical_sha(cols)
    evidence = dict(final.get("primary_metrics") or {})
    payload = {
        "version": "M77.23-DRVE-CHAMPION-METADATA-1.0",
        "champion_id": CHAMPION_ID,
        "protocol": CERTIFIED_PROTOCOL,
        "materialized_at": datetime.now(timezone.utc).isoformat(),
        "training_authority": "DEVELOPMENT_ONLY_THROUGH_2017_12_31",
        "model_family": "HistGradientBoostingClassifier",
        "feature_count": len(cols),
        "feature_columns": cols,
        "feature_registry_sha256": feature_sha,
        "model_path": MODEL_REL,
        "model_file_sha256": model_sha,
        "final_holdout_certified": True,
        "final_holdout_preregistration_sha256": final.get("preregistration_sha256"),
        "final_holdout_summary_sha256": _sha256(summary_path),
        "final_holdout_evidence": evidence,
        "no_automatic_retraining": True,
    }
    payload["model_fingerprint"] = _canonical_sha({
        "champion_id": CHAMPION_ID,
        "protocol": CERTIFIED_PROTOCOL,
        "model_file_sha256": model_sha,
        "feature_registry_sha256": feature_sha,
        "final_holdout_preregistration_sha256": final.get("preregistration_sha256"),
    })
    _atomic_json(meta_path, payload)
    return payload
