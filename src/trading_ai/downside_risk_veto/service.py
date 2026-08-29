from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from dotenv import dotenv_values

CHAMPION_ID = "DRVE-CHAMPION-001"
CERTIFIED_PROTOCOL = "M77.22.4-TRADE-BUILDER-READY-LONG-20D-BOTTOM1-VETO"
AUTHORITY_VERSION = "M77.23-CERTIFIED-DOWNSIDE-RISK-VETO-AUTHORITY-1.0"
DEFAULT_AUTHORITY = "data/downside_risk_veto/current_authority.json"
DEFAULT_CHAMPION_META = "data/downside_risk_veto/champion/DRVE-CHAMPION-001.json"

REASON_VETO = "DRV-001_EXTREME_DOWNSIDE_RISK_VETO"
REASON_AUTH_MISSING = "DRV-AUTH-001_AUTHORITY_MISSING"
REASON_AUTH_STALE = "DRV-AUTH-002_AUTHORITY_STALE"
REASON_RUN_MISMATCH = "DRV-AUTH-003_SCANNER_RUN_MISMATCH"
REASON_MODEL_MISMATCH = "DRV-AUTH-004_MODEL_FINGERPRINT_MISMATCH"
REASON_SYMBOL_MISSING = "DRV-AUTH-005_SYMBOL_SCORE_MISSING"
REASON_PARITY_INVALID = "DRV-AUTH-006_FEATURE_PARITY_INVALID"
REASON_NON_LONG = "DRV-NA-001_NON_LONG_NOT_APPLICABLE"
REASON_MODE_OFF = "DRV-OFF-001_GOVERNOR_DISABLED"
REASON_PASS = "DRV-PASS-001_OUTSIDE_EXTREME_DOWNSIDE_TAIL"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class DownsideRiskVetoDecision:
    version: str
    protocol: str
    champion_id: str
    mode: str
    applicable: bool
    authorized: bool
    blocked: bool
    status: str
    reason_codes: tuple[str, ...]
    symbol: str
    direction: str
    stock_scanner_run_id: str | None
    authority_scanner_run_id: str | None
    probability_up: float | None
    cross_section_percentile: float | None
    veto_threshold_fraction: float
    authority_generated_at: str | None
    authority_age_seconds: float | None
    model_fingerprint: str | None
    final_holdout_certified: bool
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["reason_codes"] = list(self.reason_codes)
        return out


class DownsideRiskVetoService:
    """Read-only production governor for the M77.22.4 certified veto edge.

    OFF: no production effect.
    SHADOW: evaluates and reports, never blocks.
    ENFORCE: blocks certified Trade-Builder-ready LONG handoff when vetoed and
             fails closed if current authority cannot be verified.
    """

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        mode: str | None = None,
        authority_path: str | Path | None = None,
        champion_meta_path: str | Path | None = None,
        max_age_seconds: int | None = None,
    ) -> None:
        self.root = Path(project_root or os.environ.get("TRADING_PLATFORM_ROOT") or "/Users/vinay.hatti/TradingPlatform").expanduser().resolve()
        env_file = self.root / ".env"
        file_env = dict(dotenv_values(env_file)) if env_file.exists() else {}
        def cfg(name: str, default: str | None = None):
            return os.environ.get(name) or file_env.get(name) or default
        self.mode = str(mode or cfg("M77_DOWNSIDE_RISK_VETO_MODE", "OFF")).upper()
        if self.mode not in {"OFF", "SHADOW", "ENFORCE"}:
            self.mode = "OFF"
        self.authority_path = self._resolve(authority_path or cfg("M77_DOWNSIDE_RISK_VETO_AUTHORITY", DEFAULT_AUTHORITY))
        self.champion_meta_path = self._resolve(champion_meta_path or cfg("M77_DOWNSIDE_RISK_VETO_CHAMPION_META", DEFAULT_CHAMPION_META))
        self.max_age_seconds = int(max_age_seconds or cfg("M77_DOWNSIDE_RISK_VETO_MAX_AGE_SECONDS", "10800"))

    def _resolve(self, raw: str | Path) -> Path:
        p = Path(raw).expanduser()
        return p.resolve() if p.is_absolute() else (self.root / p).resolve()

    def _decision(self, **kwargs: Any) -> DownsideRiskVetoDecision:
        base = {
            "version": AUTHORITY_VERSION,
            "protocol": CERTIFIED_PROTOCOL,
            "champion_id": CHAMPION_ID,
            "mode": self.mode,
            "applicable": True,
            "authorized": True,
            "blocked": False,
            "status": "PASS",
            "reason_codes": (REASON_PASS,),
            "symbol": "",
            "direction": "",
            "stock_scanner_run_id": None,
            "authority_scanner_run_id": None,
            "probability_up": None,
            "cross_section_percentile": None,
            "veto_threshold_fraction": 0.01,
            "authority_generated_at": None,
            "authority_age_seconds": None,
            "model_fingerprint": None,
            "final_holdout_certified": True,
            "evidence": {},
        }
        base.update(kwargs)
        return DownsideRiskVetoDecision(**base)

    def evaluate(
        self,
        *,
        symbol: str,
        direction: str,
        stock_scanner_run_id: str | None,
        trade_builder_ready: bool,
    ) -> DownsideRiskVetoDecision:
        sym = str(symbol or "").upper()
        direct = str(direction or "").upper()
        common = {"symbol": sym, "direction": direct, "stock_scanner_run_id": stock_scanner_run_id}
        if direct not in {"BULLISH", "LONG", "CALL"} or not trade_builder_ready:
            return self._decision(applicable=False, status="NOT_APPLICABLE", reason_codes=(REASON_NON_LONG,), **common)
        if self.mode == "OFF":
            return self._decision(applicable=True, status="DISABLED", reason_codes=(REASON_MODE_OFF,), **common)

        champion = self._load_json(self.champion_meta_path)
        authority = self._load_json(self.authority_path)
        failure: str | None = None
        if not champion or champion.get("champion_id") != CHAMPION_ID or champion.get("final_holdout_certified") is not True:
            failure = REASON_AUTH_MISSING
        elif not authority:
            failure = REASON_AUTH_MISSING
        elif authority.get("feature_parity_valid") is not True:
            failure = REASON_PARITY_INVALID
        elif authority.get("champion_id") != CHAMPION_ID or authority.get("model_fingerprint") != champion.get("model_fingerprint"):
            failure = REASON_MODEL_MISMATCH
        elif str(authority.get("stock_scanner_run_id") or "") != str(stock_scanner_run_id or ""):
            failure = REASON_RUN_MISMATCH
        generated = _parse_dt(None if not authority else authority.get("generated_at"))
        age = None if generated is None else max(0.0, (_utcnow() - generated).total_seconds())
        if failure is None and (age is None or age > self.max_age_seconds):
            failure = REASON_AUTH_STALE
        records = {} if not authority else dict(authority.get("records") or {})
        rec = records.get(sym)
        if failure is None and not isinstance(rec, dict):
            failure = REASON_SYMBOL_MISSING

        evidence = {} if not authority else dict(authority.get("certification_evidence") or {})
        auth_run = None if not authority else authority.get("stock_scanner_run_id")
        fp = None if not authority else authority.get("model_fingerprint")
        generated_raw = None if not authority else authority.get("generated_at")
        if failure is not None:
            block = self.mode == "ENFORCE"
            return self._decision(
                authorized=not block,
                blocked=block,
                status="AUTHORITY_UNAVAILABLE" if block else "SHADOW_AUTHORITY_UNAVAILABLE",
                reason_codes=(failure,),
                authority_scanner_run_id=auth_run,
                authority_generated_at=generated_raw,
                authority_age_seconds=age,
                model_fingerprint=fp,
                evidence=evidence,
                **common,
            )

        veto = bool(rec.get("veto"))
        probability = rec.get("probability_up")
        percentile = rec.get("cross_section_percentile")
        block = bool(veto and self.mode == "ENFORCE")
        status = "VETO" if veto else "PASS"
        if veto and self.mode == "SHADOW":
            status = "SHADOW_VETO"
        return self._decision(
            authorized=not block,
            blocked=block,
            status=status,
            reason_codes=(REASON_VETO if veto else REASON_PASS,),
            authority_scanner_run_id=auth_run,
            probability_up=None if probability is None else float(probability),
            cross_section_percentile=None if percentile is None else float(percentile),
            authority_generated_at=generated_raw,
            authority_age_seconds=age,
            model_fingerprint=fp,
            evidence=evidence,
            **common,
        )

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any] | None:
        try:
            with path.open("r", encoding="utf-8") as fh:
                value = json.load(fh)
            return value if isinstance(value, dict) else None
        except Exception:
            return None


def verify_champion_files(root: Path, metadata: dict[str, Any]) -> None:
    model_path = root / str(metadata.get("model_path") or "")
    if not model_path.exists():
        raise RuntimeError(f"Certified downside-risk champion model missing: {model_path}")
    expected = str(metadata.get("model_file_sha256") or "")
    if not expected or _sha256(model_path) != expected:
        raise RuntimeError("Certified downside-risk champion model checksum mismatch")
