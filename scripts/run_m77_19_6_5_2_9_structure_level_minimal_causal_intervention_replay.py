#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import copy
import dataclasses
import datetime as dt
import hashlib
import importlib.util
import inspect
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

VERSION = "M77.19.6.5.2.9.1-NATIVE-TYPED-COMPONENT-REHYDRATION-REPAIR-1.0"

NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"

REPORT_528_REL = "reports/m77_19_6_5_2_8_structure_and_level_generation_upstream_causal_forensics.json"
EXPECTED_528_SHA256 = "d227650425b2221da14b4e67c3bcdc0f3bc880c24909f97f75233a2e50cf0101"

REPORT_527_REL = "reports/m77_19_6_5_2_7_native_timeframe_state_and_participation_causal_intervention_replay.json"
EXPECTED_527_SHA256 = "bfba461d7b788112235a0d565bd7e0bc4e1398a6ed188022faf94357ae49835e"

PARITY_TOLERANCE = 1e-9
ARMS = (
    "CONTROL_WEEKLY_PARTICIPATION",
    "LEVELS_ONLY",
    "STRUCTURE_ONLY",
    "LEVELS_AND_STRUCTURE",
)

PARTICIPATION_PATHS = (
    "participation.evidence.adl",
    "participation.evidence.obv_normalized",
    "participation.evidence.up_down_volume_ratio",
    "participation.score",
    "participation.state",
    "participation.conviction",
    "participation.deterioration_risk",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def require_sha(root: Path, rel: str, expected: str) -> tuple[Path, Any]:
    path = root / rel
    if not path.exists():
        raise SystemExit(f"FAIL CLOSED: required authority missing: {rel}")
    actual = sha256_file(path)
    if actual != expected:
        raise SystemExit(f"FAIL CLOSED: authority SHA drift for {rel}: {actual}")
    return path, load_json(path)


def validate_528(r528: dict[str, Any]) -> dict[str, Any]:
    control = r528.get("combined_control") or {}
    checks = {
        "monthly_bundle_count_48": r528.get("monthly_bundle_count") == 48,
        "confidence_closed_48": control.get("profile_confidence_exact_count") == 48 and control.get("confidence_closed_48") is True,
        "score_closed_48": control.get("overall_score_exact_count") == 48 and control.get("score_closed_48") is True,
        "state_hash_zero_48": control.get("state_hash_exact_count") == 0 and control.get("state_hash_zero_48") is True,
        "structure_level_residual_present": int(r528.get("structure_level_residual_path_count") or 0) > 0,
        "parity_not_certified": r528.get("controlled_exact_input_parity_certified") is False,
        "reconstruction_blocked": r528.get("full_23_year_reconstruction_authorized") is False,
        "production_authority_unchanged": r528.get("production_authority_effect") is False,
    }
    checks["pass"] = all(checks.values())
    if not checks["pass"]:
        raise SystemExit(f"FAIL CLOSED: M77.19.6.5.2.8 authority contract drift: {checks}")
    return checks


def validate_527(r527: dict[str, Any]) -> dict[str, Any]:
    findings = r527.get("causal_findings") or {}
    checks = {
        "combined_score_closed": findings.get("full_score_parity_after_combined_repair") is True,
        "combined_state_open": findings.get("full_state_parity_after_combined_repair") is False,
        "parity_not_certified": r527.get("controlled_exact_input_parity_certified") is False,
        "reconstruction_blocked": r527.get("full_23_year_reconstruction_authorized") is False,
        "production_authority_unchanged": r527.get("production_authority_effect") is False,
    }
    checks["pass"] = all(checks.values())
    if not checks["pass"]:
        raise SystemExit(f"FAIL CLOSED: M77.19.6.5.2.7 authority contract drift: {checks}")
    return checks


@contextlib.contextmanager
def readonly_session():
    from trading_ai.database.session import SessionLocal
    from sqlalchemy import text
    session = SessionLocal()
    try:
        session.execute(text("SET TRANSACTION READ ONLY"))
        yield session
        session.rollback()
    finally:
        session.close()


def load_spy_sessions() -> set[dt.date]:
    from sqlalchemy import text
    with readonly_session() as session:
        rows = session.execute(text("""
            SELECT date
            FROM public.price_history
            WHERE symbol = 'SPY'
            ORDER BY date
        """)).all()
    out: set[dt.date] = set()
    for (value,) in rows:
        if isinstance(value, dt.datetime):
            value = value.date()
        elif not isinstance(value, dt.date):
            value = dt.date.fromisoformat(str(value)[:10])
        out.add(value)
    if not out:
        raise SystemExit("FAIL CLOSED: SPY session calendar empty")
    return out


def import_native(root: Path):
    path = root / NATIVE_RUNNER_REL
    if not path.exists():
        raise SystemExit("FAIL CLOSED: native runner missing")
    actual = sha256_file(path)
    if actual != EXPECTED_NATIVE_RUNNER_SHA256:
        raise SystemExit(f"FAIL CLOSED: native runner SHA drift: {actual}")
    spec = importlib.util.spec_from_file_location("m77_native_529", path)
    if spec is None or spec.loader is None:
        raise SystemExit("FAIL CLOSED: native runner import unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("call_profile", "compare_profile", "StockIntelligenceService"):
        if not hasattr(module, name):
            raise SystemExit(f"FAIL CLOSED: native runner missing {name}")
    return module


def normalize_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for raw in bundle["price_history"]:
        low = {str(k).lower(): v for k, v in raw.items()}
        date_value = low.get("date") or low.get("session_date") or low.get("price_date") or low.get("bar_date") or low.get("as_of")
        if date_value is None:
            continue
        if isinstance(date_value, dt.datetime):
            date_value = date_value.date()
        elif not isinstance(date_value, dt.date):
            date_value = dt.date.fromisoformat(str(date_value)[:10])

        def number(name: str):
            value = low.get(name)
            if value in (None, ""):
                return None
            return float(value)

        row = {
            "date": date_value,
            "open": number("open"),
            "high": number("high"),
            "low": number("low"),
            "close": number("close"),
            "volume": number("volume"),
        }
        if row["close"] is not None:
            rows.append(row)
    rows.sort(key=lambda x: x["date"])
    if not rows:
        raise RuntimeError("no normalized price history")
    return rows


def get_member(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def set_member(obj: Any, key: str, value: Any) -> None:
    if isinstance(obj, dict):
        obj[key] = copy.deepcopy(value)
    else:
        setattr(obj, key, copy.deepcopy(value))


def get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        cur = get_member(cur, part)
    return cur


def set_path(obj: Any, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        cur = get_member(cur, part)
    set_member(cur, parts[-1], value)


def patch_mt(service: Any, frozen_profile: dict[str, Any]) -> Callable[[], None]:
    original = service.mt.analyze

    def wrapped(data_by_timeframe):
        result = original(data_by_timeframe)
        states = result.get("states")
        if not isinstance(states, dict) or "1w" not in states:
            raise RuntimeError("MT output missing 1w")
        fw = frozen_profile["timeframe_states"]["1w"]
        set_path(states["1w"], "confidence", fw["confidence"])
        set_path(states["1w"], "evidence.ema50", fw["evidence"]["ema50"])
        confs = [float(get_path(v, "confidence")) for v in states.values()]
        result["confidence"] = round(sum(confs) / len(confs), 2)
        return result

    service.mt.analyze = wrapped
    return lambda: setattr(service.mt, "analyze", original)


def patch_participation(service: Any, frozen_profile: dict[str, Any]) -> Callable[[], None]:
    original = service.part.analyze
    frozen = frozen_profile["participation"]

    def wrapped(primary):
        result = original(primary)
        for full in PARTICIPATION_PATHS:
            suffix = full.removeprefix("participation.")
            set_path(result, suffix, get_path(frozen, suffix))
        return result

    service.part.analyze = wrapped
    return lambda: setattr(service.part, "analyze", original)


def _construct_native_component(native_type: type, payload: Any) -> Any:
    """
    Rehydrate a JSON-frozen component into the exact native runtime class.

    Historical bundles necessarily persist components as JSON objects. Native
    Stock Intelligence services pass typed dataclass/model objects downstream.
    Synthetic intervention is valid only if it preserves that native type
    contract; plain dict injection is explicitly forbidden.
    """
    if not isinstance(payload, dict):
        return copy.deepcopy(payload)

    data = copy.deepcopy(payload)

    if dataclasses.is_dataclass(native_type):
        field_names = {field.name for field in dataclasses.fields(native_type)}
        kwargs = {key: value for key, value in data.items() if key in field_names}
        try:
            return native_type(**kwargs)
        except Exception as exc:
            raise RuntimeError(
                f"FAIL CLOSED: dataclass rehydration failed for "
                f"{native_type.__module__}.{native_type.__qualname__}: {exc}"
            ) from exc

    for method_name in ("model_validate", "parse_obj", "from_dict", "from_json_dict"):
        method = getattr(native_type, method_name, None)
        if callable(method):
            try:
                return method(data)
            except Exception:
                pass

    try:
        signature = inspect.signature(native_type)
        accepted = {
            name
            for name, parameter in signature.parameters.items()
            if name != "self"
            and parameter.kind
            in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        }
        has_var_kw = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
        kwargs = data if has_var_kw else {k: v for k, v in data.items() if k in accepted}
        return native_type(**kwargs)
    except Exception:
        pass

    try:
        obj = native_type.__new__(native_type)
        for key, value in data.items():
            setattr(obj, key, copy.deepcopy(value))
        return obj
    except Exception as exc:
        raise RuntimeError(
            f"FAIL CLOSED: unable to rehydrate frozen component into native type "
            f"{native_type.__module__}.{native_type.__qualname__}: {exc}"
        ) from exc


def _native_component_type(
    primary_native: list[Any],
    secondary_native: list[Any] | None,
    label: str,
) -> type:
    candidates = list(primary_native or []) + list(secondary_native or [])
    for item in candidates:
        if not isinstance(item, dict):
            return type(item)
    raise RuntimeError(
        f"FAIL CLOSED: cannot resolve native {label} component type from native output"
    )


def rehydrate_native_sequence(
    frozen_items: list[Any],
    primary_native: list[Any],
    secondary_native: list[Any] | None = None,
    *,
    label: str,
    required_attributes: tuple[str, ...] = (),
) -> list[Any]:
    if not isinstance(frozen_items, list):
        raise RuntimeError(f"FAIL CLOSED: frozen {label} payload is not a list")

    if not frozen_items:
        return []

    native_type = _native_component_type(primary_native, secondary_native, label)
    result = [
        _construct_native_component(native_type, item)
        for item in frozen_items
    ]

    for index, item in enumerate(result):
        if not isinstance(item, native_type):
            raise RuntimeError(
                f"FAIL CLOSED: {label}[{index}] type mismatch after rehydration"
            )
        for attribute in required_attributes:
            if not hasattr(item, attribute):
                raise RuntimeError(
                    f"FAIL CLOSED: rehydrated {label}[{index}] missing native "
                    f"attribute {attribute!r}"
                )

    return result


def patch_levels(service: Any, frozen_profile: dict[str, Any]) -> Callable[[], None]:
    original = service.levels.analyze
    frozen_support = frozen_profile["support_levels"]
    frozen_resistance = frozen_profile["resistance_levels"]

    def wrapped(data_by_timeframe):
        result = original(data_by_timeframe)
        if not isinstance(result, dict):
            raise RuntimeError("level output is not a dict")
        if "support_levels" not in result or "resistance_levels" not in result:
            raise RuntimeError("level output contract missing support/resistance")

        native_support = list(result.get("support_levels") or [])
        native_resistance = list(result.get("resistance_levels") or [])

        result = copy.deepcopy(result)
        result["support_levels"] = rehydrate_native_sequence(
            frozen_support,
            native_support,
            native_resistance,
            label="support_levels",
            required_attributes=("price",),
        )
        result["resistance_levels"] = rehydrate_native_sequence(
            frozen_resistance,
            native_resistance,
            native_support,
            label="resistance_levels",
            required_attributes=("price",),
        )

        if any(isinstance(item, dict) for item in result["support_levels"]):
            raise RuntimeError("FAIL CLOSED: dict support level leaked into native pipeline")
        if any(isinstance(item, dict) for item in result["resistance_levels"]):
            raise RuntimeError("FAIL CLOSED: dict resistance level leaked into native pipeline")

        return result

    service.levels.analyze = wrapped
    return lambda: setattr(service.levels, "analyze", original)


def patch_structure(service: Any, frozen_profile: dict[str, Any]) -> Callable[[], None]:
    original = service.structure_zones.build
    frozen_zones = frozen_profile["structure_zones"]

    def wrapped(profile):
        # Execute native builder first so the intervention changes only the
        # component output, not call ordering, exceptions, or side effects.
        native_zones = original(profile)
        native_zones = list(native_zones or [])

        rehydrated = rehydrate_native_sequence(
            frozen_zones,
            native_zones,
            None,
            label="structure_zones",
            required_attributes=("lower_bound", "upper_bound"),
        )

        if any(isinstance(item, dict) for item in rehydrated):
            raise RuntimeError("FAIL CLOSED: dict structure zone leaked into native pipeline")

        return rehydrated

    service.structure_zones.build = wrapped
    return lambda: setattr(service.structure_zones, "build", original)


def jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        value = dataclasses.asdict(value)
    elif hasattr(value, "model_dump") and callable(value.model_dump):
        value = value.model_dump()
    elif hasattr(value, "dict") and callable(value.dict):
        try:
            value = value.dict()
        except Exception:
            pass
    elif not isinstance(value, (dict, list, tuple, str, int, float, bool, type(None), dt.date, dt.datetime)):
        if hasattr(value, "__dict__"):
            value = vars(value)

    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def state_projection(profile: Any) -> dict[str, Any]:
    p = jsonable(profile)
    return {
        "support_levels": p.get("support_levels"),
        "resistance_levels": p.get("resistance_levels"),
        "structure_zones": p.get("structure_zones"),
        "trade_plan": p.get("trade_plan"),
        "decision_intelligence": p.get("decision_intelligence"),
        "state_hash": p.get("state_hash"),
    }


def stable_json_hash(value: Any) -> str:
    payload = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def run_arm(native, arm: str, symbol: str, rows: list[dict[str, Any]], as_of: dt.date, sessions: set[dt.date], frozen_output: dict[str, Any], frozen_profile: dict[str, Any]) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    if arm not in ARMS:
        raise RuntimeError(f"unknown intervention arm: {arm}")
    service = native.StockIntelligenceService()
    restores: list[Callable[[], None]] = []
    restores.append(patch_mt(service, frozen_profile))
    restores.append(patch_participation(service, frozen_profile))
    if arm in ("LEVELS_ONLY", "LEVELS_AND_STRUCTURE"):
        restores.append(patch_levels(service, frozen_profile))
    if arm in ("STRUCTURE_ONLY", "LEVELS_AND_STRUCTURE"):
        restores.append(patch_structure(service, frozen_profile))

    try:
        profile = native.call_profile(service, symbol, rows, as_of, sessions, 300, 750)
    finally:
        for restore in reversed(restores):
            restore()

    if profile is None:
        raise RuntimeError(f"profile ineligible for {symbol} / {arm}")
    comparison = native.compare_profile(profile, frozen_output)
    projection = state_projection(profile)
    return profile, comparison, projection


def exact_component_count(records: list[dict[str, Any]], arm: str, key: str) -> int:
    return sum(bool(r["arms"][arm][key]) for r in records)


def summarize_arm(records: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    items = [r["arms"][arm] for r in records]
    return {
        "count": len(items),
        "direction_match_pct": 100.0 * sum(i["direction_match"] for i in items) / len(items),
        "profile_confidence_exact_count": sum(i["confidence_abs_error"] <= PARITY_TOLERANCE for i in items),
        "overall_score_exact_count": sum(i["score_abs_error"] <= PARITY_TOLERANCE for i in items),
        "state_hash_exact_count": sum(i["state_hash_match"] for i in items),
        "support_levels_exact_count": sum(i["support_levels_exact"] for i in items),
        "resistance_levels_exact_count": sum(i["resistance_levels_exact"] for i in items),
        "structure_zones_exact_count": sum(i["structure_zones_exact"] for i in items),
        "trade_plan_exact_count": sum(i["trade_plan_exact"] for i in items),
        "decision_intelligence_exact_count": sum(i["decision_intelligence_exact"] for i in items),
        "max_confidence_abs_error": max(float(i["confidence_abs_error"]) for i in items),
        "max_score_abs_error": max(float(i["score_abs_error"]) for i in items),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--bundle-root", default="research_data/m77_19_6_4_2/exact_frozen_input_context_bundles")
    parser.add_argument("--output", default="reports/m77_19_6_5_2_9_structure_level_minimal_causal_intervention_replay.json")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    p528, r528 = require_sha(root, REPORT_528_REL, EXPECTED_528_SHA256)
    p527, r527 = require_sha(root, REPORT_527_REL, EXPECTED_527_SHA256)
    authority_528 = validate_528(r528)
    authority_527 = validate_527(r527)

    native = import_native(root)
    sessions = load_spy_sessions()
    monthly_files = sorted((root / args.bundle_root / "monthly").glob("*.json"))
    if len(monthly_files) != 48:
        raise SystemExit(f"FAIL CLOSED: expected 48 monthly bundles, found {len(monthly_files)}")

    records: list[dict[str, Any]] = []
    for file_path in monthly_files:
        bundle = load_json(file_path)
        frozen_profile = bundle["frozen_profile"]
        frozen_output = bundle["frozen_output"]
        identity = bundle["prediction_identity"]
        symbol = str(identity["symbol"])
        as_of = dt.date.fromisoformat(str(identity["as_of"])[:10])
        rows = normalize_rows(bundle)
        frozen_projection = {
            "support_levels": frozen_profile.get("support_levels"),
            "resistance_levels": frozen_profile.get("resistance_levels"),
            "structure_zones": frozen_profile.get("structure_zones"),
            "trade_plan": frozen_profile.get("trade_plan"),
            "decision_intelligence": frozen_profile.get("decision_intelligence"),
            "state_hash": frozen_profile.get("state_hash"),
        }
        frozen_hashes = {k: stable_json_hash(v) for k, v in frozen_projection.items() if k != "state_hash"}

        arm_results: dict[str, Any] = {}
        for arm in ARMS:
            profile, comparison, projection = run_arm(native, arm, symbol, rows, as_of, sessions, frozen_output, frozen_profile)
            item = {
                "direction_match": bool(comparison["direction_match"]),
                "confidence_abs_error": float(comparison["confidence_abs_error"]),
                "score_abs_error": float(comparison["score_abs_error"]),
                "state_hash_match": bool(comparison["state_hash_match"]),
                "support_levels_exact": stable_json_hash(projection["support_levels"]) == frozen_hashes["support_levels"],
                "resistance_levels_exact": stable_json_hash(projection["resistance_levels"]) == frozen_hashes["resistance_levels"],
                "structure_zones_exact": stable_json_hash(projection["structure_zones"]) == frozen_hashes["structure_zones"],
                "trade_plan_exact": stable_json_hash(projection["trade_plan"]) == frozen_hashes["trade_plan"],
                "decision_intelligence_exact": stable_json_hash(projection["decision_intelligence"]) == frozen_hashes["decision_intelligence"],
            }
            arm_results[arm] = item

        control = arm_results["CONTROL_WEEKLY_PARTICIPATION"]
        if control["confidence_abs_error"] > PARITY_TOLERANCE:
            raise SystemExit(f"FAIL CLOSED: control confidence closure regressed for {symbol}")
        if control["score_abs_error"] > PARITY_TOLERANCE:
            raise SystemExit(f"FAIL CLOSED: control score closure regressed for {symbol}")
        if control["state_hash_match"]:
            raise SystemExit(f"FAIL CLOSED: control state hash unexpectedly matched for {symbol}")

        for arm in ARMS[1:]:
            if arm_results[arm]["confidence_abs_error"] > PARITY_TOLERANCE:
                raise SystemExit(f"FAIL CLOSED: intervention changed closed confidence for {symbol} / {arm}")
            # Score may legitimately change under levels-only or structure-only; it must be measured, not assumed.

        records.append({
            "bundle": str(file_path.relative_to(root)),
            "symbol": symbol,
            "as_of": as_of.isoformat(),
            "arms": arm_results,
        })

    summaries = {arm: summarize_arm(records, arm) for arm in ARMS}
    control = summaries["CONTROL_WEEKLY_PARTICIPATION"]
    levels = summaries["LEVELS_ONLY"]
    structure = summaries["STRUCTURE_ONLY"]
    combined = summaries["LEVELS_AND_STRUCTURE"]

    causal_findings = {
        "control_confidence_closed_48": control["profile_confidence_exact_count"] == 48,
        "control_score_closed_48": control["overall_score_exact_count"] == 48,
        "control_state_open_48": control["state_hash_exact_count"] == 0,
        "levels_intervention_exact_48": levels["support_levels_exact_count"] == 48 and levels["resistance_levels_exact_count"] == 48,
        "structure_intervention_exact_48": structure["structure_zones_exact_count"] == 48,
        "combined_levels_structure_exact_48": combined["support_levels_exact_count"] == 48 and combined["resistance_levels_exact_count"] == 48 and combined["structure_zones_exact_count"] == 48,
        "levels_restore_structure_gain": levels["structure_zones_exact_count"] - control["structure_zones_exact_count"],
        "levels_restore_state_hash_gain": levels["state_hash_exact_count"] - control["state_hash_exact_count"],
        "structure_restore_state_hash_gain": structure["state_hash_exact_count"] - control["state_hash_exact_count"],
        "combined_restore_state_hash_gain": combined["state_hash_exact_count"] - control["state_hash_exact_count"],
        "levels_restore_trade_plan_gain": levels["trade_plan_exact_count"] - control["trade_plan_exact_count"],
        "structure_restore_trade_plan_gain": structure["trade_plan_exact_count"] - control["trade_plan_exact_count"],
        "combined_restore_trade_plan_gain": combined["trade_plan_exact_count"] - control["trade_plan_exact_count"],
        "levels_restore_decision_gain": levels["decision_intelligence_exact_count"] - control["decision_intelligence_exact_count"],
        "structure_restore_decision_gain": structure["decision_intelligence_exact_count"] - control["decision_intelligence_exact_count"],
        "combined_restore_decision_gain": combined["decision_intelligence_exact_count"] - control["decision_intelligence_exact_count"],
        "full_state_parity_after_combined": combined["state_hash_exact_count"] == 48,
        "full_score_parity_after_combined": combined["overall_score_exact_count"] == 48,
        "full_confidence_parity_after_combined": combined["profile_confidence_exact_count"] == 48,
    }

    if causal_findings["full_state_parity_after_combined"] and causal_findings["full_score_parity_after_combined"] and causal_findings["full_confidence_parity_after_combined"]:
        conclusion = "MONTHLY_STATE_PARITY_CAUSALLY_CLOSED_BY_WEEKLY_PARTICIPATION_PLUS_LEVELS_AND_STRUCTURE_COMPONENT_OUTPUTS"
        next_step = "BUILD_M77_19_6_5_2_10_STRICT_FULL_PROFILE_SEMANTIC_PARITY_CERTIFICATION"
    elif causal_findings["levels_restore_structure_gain"] > 0:
        conclusion = "LEVEL_GENERATION_CAUSALLY_DRIVES_STRUCTURE_DIVERGENCE_BUT_FULL_STATE_PARITY_REMAINS_OPEN"
        next_step = "BUILD_M77_19_6_5_2_10_LEVEL_GENERATION_INPUT_AND_SELECTION_SEMANTICS_FORENSICS"
    elif causal_findings["structure_restore_state_hash_gain"] > 0 or causal_findings["combined_restore_state_hash_gain"] > 0:
        conclusion = "STRUCTURE_COMPONENT_HAS_CAUSAL_STATE_EFFECT_BUT_UPSTREAM_LEVEL_TO_STRUCTURE_CHAIN_IS_NOT_SUFFICIENTLY_CLOSED"
        next_step = "BUILD_M77_19_6_5_2_10_STRUCTURE_BUILD_INPUT_SEMANTICS_FORENSICS"
    else:
        conclusion = "STRUCTURE_LEVEL_COMPONENT_INTERVENTIONS_DO_NOT_CLOSE_STATE_HASH; RESIDUAL_HASH_PAYLOAD_OR_OTHER_UPSTREAM_DOMAINS_REMAIN"
        next_step = "BUILD_M77_19_6_5_2_10_STATE_HASH_PAYLOAD_AND_RESIDUAL_DOMAIN_CAUSAL_FORENSICS"

    report = {
        "version": VERSION,
        "source_authorities": {
            "m77_19_6_5_2_8": {"path": str(p528), "sha256": EXPECTED_528_SHA256},
            "m77_19_6_5_2_7": {"path": str(p527), "sha256": EXPECTED_527_SHA256},
            "native_runner": {"path": str(root / NATIVE_RUNNER_REL), "sha256": EXPECTED_NATIVE_RUNNER_SHA256},
        },
        "governance": {
            "research_only": True,
            "synthetic_component_output_interventions_only": True,
            "native_typed_component_rehydration_required": True,
            "plain_dict_component_injection_allowed": False,
            "database_mode": "READ_ONLY_SPY_SESSION_CALENDAR_ONLY",
            "production_database_writes": False,
            "parity_tolerance": PARITY_TOLERANCE,
            "parity_thresholds_relaxed": False,
            "native_compare_profile_is_semantic_authority": True,
            "production_authority_effect": False,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
        },
        "authority_validation": {"m77_19_6_5_2_8": authority_528, "m77_19_6_5_2_7": authority_527},
        "intervention_contract": {
            "control": "weekly confidence + weekly ema50 + participation component outputs",
            "levels_only": "control + frozen support_levels/resistance_levels injected at LevelIntelligenceService output; native structure/downstream recompute",
            "structure_only": "control + frozen structure_zones injected at InstitutionalStructureZoneEngine output; native levels and downstream recompute",
            "levels_and_structure": "control + both interventions; all scoring/trade-plan/certification/decision stages recompute natively",
            "demand_supply_zones_not_replaced_in_levels_only": True,
            "native_structure_builder_executes_before_structure_output_replacement": True,
            "frozen_support_resistance_rehydrated_to_native_runtime_type": True,
            "frozen_structure_zones_rehydrated_to_native_runtime_type": True,
        },
        "monthly_bundle_count": len(records),
        "arm_summaries": summaries,
        "causal_findings": causal_findings,
        "records": records,
        "forensic_conclusion": conclusion,
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": next_step,
    }

    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")

    print("=== M77.19.6.5.2.9 STRUCTURE / LEVEL MINIMAL CAUSAL INTERVENTION REPLAY ===")
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("authority_528:", authority_528)
    print("authority_527:", authority_527)
    for arm in ARMS:
        print(arm, summaries[arm])
    print("causal_findings:", causal_findings)
    print("forensic_conclusion:", conclusion)
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", next_step)
    print("report:", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
