#!/usr/bin/env python3
"""
M77.19.6.5.2 — Native Controlled Execution & Strict Parity Certification

Consumes exact frozen bundles from M77.19.6.4.2 and executes the certified
native replay semantics recovered by M77.19.6.5.1.1.

Execution authority:
  - Stock Intelligence profile computation: exact call_profile(...) from
    scripts/run_m77_19_6_isolated_replay_engine_parity.py
  - StockIntelligenceService() construction from the same native runner
  - session_set reconstructed READ ONLY from production SPY price_history
  - bundle price_history supplies the symbol's exact frozen production input
  - M77.19.4 isolated adapter source SHA-256 is verified as provenance for the
    certified PIT/cadence contract, but snapshot() is not substituted for
    Stock Intelligence profile computation.

Strict certification:
  * exactly 48 successful comparisons per cadence
  * direction 100%
  * overall_score max abs error <= 1e-9
  * confidence max abs error <= 1e-9
  * canonical semantic profile hash 100%
  * deterministic repeat 100%

No production writes. No threshold relaxation. Full 23-year reconstruction
remains blocked in this package regardless of result; a separate authorization
gate is required after successful certification.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import importlib.util
import json
import math
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

VERSION = "M77.19.6.5.2-NATIVE-CONTROLLED-EXECUTION-PARITY-CERTIFICATION-1.0"

CADENCES = ("DAILY", "WEEKLY", "MONTHLY")
SCORE_EPSILON = 1e-9
CONFIDENCE_EPSILON = 1e-9
DIRECTION_REQUIRED_PCT = 100.0
SEMANTIC_HASH_REQUIRED_PCT = 100.0
DETERMINISTIC_REPEAT_REQUIRED_PCT = 100.0
REQUIRED_COMPARISONS_PER_CADENCE = 48

NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
CERTIFIED_DM_ADAPTER_REL = "src/trading_ai/historical_underlying_replay/m77_19_4_isolated_adapters.py"

EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"
EXPECTED_DM_ADAPTER_SHA256 = "ba9d0f03f22252f719afd34d4257e951e2f327d732c082bc57ffcebd359751ea"

NON_SEMANTIC_KEYS = {
    "id", "run_id", "replay_run_id", "snapshot_id", "state_id",
    "publication_id", "request_id", "trace_id", "correlation_id",
    "generated_at", "created_at", "updated_at", "published_at",
    "snapshot_timestamp", "computed_at", "calculated_at", "ingested_at",
    "uuid", "nonce",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def jsonable(v: Any) -> Any:
    if is_dataclass(v):
        return jsonable(asdict(v))
    if isinstance(v, Mapping):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [jsonable(x) for x in v]
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if hasattr(v, "value") and not isinstance(v, (str, bytes, int, float, bool)):
        try:
            return jsonable(v.value)
        except Exception:
            pass
    if hasattr(v, "__dict__") and not isinstance(v, type):
        try:
            return jsonable(vars(v))
        except Exception:
            pass
    if isinstance(v, float):
        if math.isnan(v): return "NaN"
        if math.isinf(v): return "Infinity" if v > 0 else "-Infinity"
    return v


def semantic_projection(v: Any) -> Any:
    if isinstance(v, Mapping):
        out = {}
        for key, value in v.items():
            lk = str(key).lower()
            if (
                lk in NON_SEMANTIC_KEYS
                or lk.endswith("_uuid")
                or lk.endswith("_run_id")
                or lk.endswith("_snapshot_id")
                or lk.endswith("_generated_at")
                or lk.endswith("_created_at")
            ):
                continue
            out[str(key)] = semantic_projection(value)
        return out
    if isinstance(v, (list, tuple)):
        return [semantic_projection(x) for x in v]
    return jsonable(v)


def semantic_hash(v: Any) -> str:
    payload = json.dumps(
        semantic_projection(v),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def require_prior(root: Path, explicit: str | None) -> tuple[Path, dict[str, Any]]:
    candidates = [Path(explicit)] if explicit else []
    candidates.append(
        root / "reports" / "m77_19_6_5_1_1_imported_native_contract_resolution.json"
    )
    for path in candidates:
        if not path.exists():
            continue
        doc = load_json(path)
        if doc.get("native_invocation_contract_ready") is not True:
            raise SystemExit("FAIL CLOSED: native invocation contract is not READY")
        if doc.get("full_23_year_reconstruction_authorized") is True:
            raise SystemExit("FAIL CLOSED: unexpected prior 23-year authorization")
        if doc.get("production_authority_effect") is True:
            raise SystemExit("FAIL CLOSED: unexpected prior production effect")
        if doc.get("next_step") != "BUILD_M77_19_6_5_2_NATIVE_CONTROLLED_EXECUTION_AND_PARITY_CERTIFICATION":
            raise SystemExit("FAIL CLOSED: prior report does not authorize M77.19.6.5.2")
        return path, doc
    raise SystemExit("FAIL CLOSED: M77.19.6.5.1.1 report not found")


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


def load_spy_session_set() -> set[dt.date]:
    from sqlalchemy import text

    with readonly_session() as session:
        rows = session.execute(
            text(
                """
                SELECT date
                FROM public.price_history
                WHERE symbol = 'SPY'
                ORDER BY date
                """
            )
        ).all()

    out = set()
    for row in rows:
        value = row[0]
        if isinstance(value, dt.datetime):
            value = value.date()
        elif not isinstance(value, dt.date):
            value = dt.date.fromisoformat(str(value)[:10])
        out.add(value)

    if not out:
        raise SystemExit("FAIL CLOSED: no SPY session calendar rows recovered")

    return out


def import_native_runner(root: Path):
    path = root / NATIVE_RUNNER_REL
    if not path.exists():
        raise SystemExit("FAIL CLOSED: native M77.19.6 runner missing")

    actual = sha256_file(path)
    if actual != EXPECTED_NATIVE_RUNNER_SHA256:
        raise SystemExit(
            f"FAIL CLOSED: native runner SHA-256 drift: {actual}"
        )

    spec = importlib.util.spec_from_file_location(
        "m77_19_6_native_runner_for_652",
        path,
    )
    if spec is None or spec.loader is None:
        raise SystemExit("FAIL CLOSED: cannot import native runner")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    required = (
        "call_profile",
        "compare_profile",
        "StockIntelligenceService",
    )
    for name in required:
        if not hasattr(module, name):
            raise SystemExit(f"FAIL CLOSED: native runner missing {name}")

    return module


def verify_dm_adapter_provenance(root: Path) -> str:
    path = root / CERTIFIED_DM_ADAPTER_REL
    if not path.exists():
        raise SystemExit("FAIL CLOSED: certified M77.19.4 adapter module missing")
    actual = sha256_file(path)
    if actual != EXPECTED_DM_ADAPTER_SHA256:
        raise SystemExit(
            f"FAIL CLOSED: certified M77.19.4 adapter SHA-256 drift: {actual}"
        )
    return actual


def normalize_bundle_rows(bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []

    for raw in bundle["price_history"]:
        low = {str(k).lower(): v for k, v in raw.items()}

        date_value = (
            low.get("date")
            or low.get("session_date")
            or low.get("price_date")
            or low.get("bar_date")
            or low.get("as_of")
        )

        if date_value is None:
            continue

        if isinstance(date_value, dt.datetime):
            date_value = date_value.date()
        elif not isinstance(date_value, dt.date):
            date_value = dt.date.fromisoformat(str(date_value)[:10])

        def f(name: str):
            value = low.get(name)
            if value is None or value == "":
                return None
            return float(value)

        row = {
            "date": date_value,
            "open": f("open"),
            "high": f("high"),
            "low": f("low"),
            "close": f("close"),
            "volume": f("volume"),
        }

        if row["close"] is None:
            continue

        rows.append(row)

    rows.sort(key=lambda x: x["date"])
    return rows


def profile_to_mapping(profile: Any) -> dict[str, Any]:
    data = jsonable(profile)
    if not isinstance(data, Mapping):
        raise ValueError("profile did not normalize to mapping")
    return dict(data)


def frozen_profile_mapping(bundle: Mapping[str, Any]) -> dict[str, Any]:
    value = bundle.get("frozen_profile")
    if not isinstance(value, Mapping):
        raise ValueError("frozen_profile is not a mapping")
    return dict(value)


def lookup(mapping: Mapping[str, Any], *names: str) -> Any:
    low = {str(k).lower(): k for k in mapping}
    for name in names:
        if name.lower() in low:
            return mapping[low[name.lower()]]
    return None


def compare_native(
    bundle: Mapping[str, Any],
    first: Any,
    second: Any,
) -> dict[str, Any]:
    isolated = profile_to_mapping(first)
    repeat = profile_to_mapping(second)
    frozen_profile = frozen_profile_mapping(bundle)
    frozen_output = bundle["frozen_output"]

    isolated_direction = lookup(isolated, "direction")
    isolated_score = lookup(isolated, "overall_score", "score")
    isolated_confidence = lookup(isolated, "confidence", "confidence_score")

    if isolated_direction is None:
        raise ValueError("isolated direction missing")
    if isolated_score is None:
        raise ValueError("isolated score missing")
    if isolated_confidence is None:
        raise ValueError("isolated confidence missing")

    frozen_direction = frozen_output["direction"]
    frozen_score = frozen_output["overall_score"]
    frozen_confidence = frozen_output["confidence"]

    frozen_sem_hash = semantic_hash(frozen_profile)
    isolated_sem_hash = semantic_hash(isolated)

    return {
        "prediction_id": bundle["prediction_identity"]["prediction_id"],
        "symbol": bundle["prediction_identity"]["symbol"],
        "as_of": bundle["prediction_identity"]["as_of"],
        "stored_direction": frozen_direction,
        "isolated_direction": isolated_direction,
        "direction_match": str(frozen_direction) == str(isolated_direction),
        "stored_overall_score": float(frozen_score),
        "isolated_overall_score": float(isolated_score),
        "score_abs_error": abs(float(frozen_score) - float(isolated_score)),
        "stored_confidence": float(frozen_confidence),
        "isolated_confidence": float(isolated_confidence),
        "confidence_abs_error": abs(float(frozen_confidence) - float(isolated_confidence)),
        "stored_semantic_hash": frozen_sem_hash,
        "isolated_semantic_hash": isolated_sem_hash,
        "semantic_hash_match": frozen_sem_hash == isolated_sem_hash,
        "deterministic_repeat": semantic_hash(isolated) == semantic_hash(repeat),
        "stored_raw_state_hash": frozen_output.get("state_hash"),
        "isolated_profile": isolated,
    }


def summarize(evidence: list[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(evidence)
    if n == 0:
        return {
            "comparisons": 0,
            "direction_match_pct": 0.0,
            "semantic_hash_match_pct": 0.0,
            "deterministic_repeat_pct": 0.0,
            "max_score_abs_error": None,
            "max_confidence_abs_error": None,
            "pass": False,
        }

    direction_pct = 100.0 * sum(x["direction_match"] for x in evidence) / n
    semantic_pct = 100.0 * sum(x["semantic_hash_match"] for x in evidence) / n
    repeat_pct = 100.0 * sum(x["deterministic_repeat"] for x in evidence) / n
    max_score = max(x["score_abs_error"] for x in evidence)
    max_conf = max(x["confidence_abs_error"] for x in evidence)

    passed = (
        n == REQUIRED_COMPARISONS_PER_CADENCE
        and direction_pct == DIRECTION_REQUIRED_PCT
        and max_score <= SCORE_EPSILON
        and max_conf <= CONFIDENCE_EPSILON
        and semantic_pct == SEMANTIC_HASH_REQUIRED_PCT
        and repeat_pct == DETERMINISTIC_REPEAT_REQUIRED_PCT
    )

    return {
        "comparisons": n,
        "direction_match_pct": direction_pct,
        "semantic_hash_match_pct": semantic_pct,
        "deterministic_repeat_pct": repeat_pct,
        "max_score_abs_error": max_score,
        "max_confidence_abs_error": max_conf,
        "pass": passed,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--prior-report")
    ap.add_argument(
        "--bundle-root",
        default="research_data/m77_19_6_4_2/exact_frozen_input_context_bundles",
    )
    ap.add_argument(
        "--output",
        default="reports/m77_19_6_5_2_native_controlled_execution_parity_certification.json",
    )
    args = ap.parse_args()

    root = Path(args.project_root).resolve()

    prior_path, _ = require_prior(root, args.prior_report)
    dm_sha = verify_dm_adapter_provenance(root)
    native = import_native_runner(root)
    session_set = load_spy_session_set()

    service = native.StockIntelligenceService()

    report = {
        "version": VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "prior_report": str(prior_path),
        "governance": {
            "research_only": True,
            "database_mode": "READ_ONLY_SPY_SESSION_CALENDAR_ONLY",
            "production_database_writes": False,
            "native_runner_sha256_frozen": EXPECTED_NATIVE_RUNNER_SHA256,
            "certified_dm_adapter_sha256_frozen": EXPECTED_DM_ADAPTER_SHA256,
            "parity_thresholds_relaxed": False,
            "score_epsilon": SCORE_EPSILON,
            "confidence_epsilon": CONFIDENCE_EPSILON,
            "direction_required_pct": DIRECTION_REQUIRED_PCT,
            "semantic_hash_required_pct": SEMANTIC_HASH_REQUIRED_PCT,
            "deterministic_repeat_required_pct": DETERMINISTIC_REPEAT_REQUIRED_PCT,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
        "native_contract": {
            "runner": NATIVE_RUNNER_REL,
            "runner_sha256": EXPECTED_NATIVE_RUNNER_SHA256,
            "callable": "call_profile",
            "service": "StockIntelligenceService()",
            "session_calendar": "READ_ONLY public.price_history WHERE symbol='SPY'",
            "certified_pit_adapter": CERTIFIED_DM_ADAPTER_REL,
            "certified_pit_adapter_sha256": dm_sha,
        },
        "spy_session_count": len(session_set),
        "cadences": {},
        "blockers": [],
    }

    bundle_root = root / args.bundle_root

    for cadence in CADENCES:
        files = sorted((bundle_root / cadence.lower()).glob("*.json"))
        evidence = []
        errors = []

        if len(files) != REQUIRED_COMPARISONS_PER_CADENCE:
            report["blockers"].append(
                f"{cadence}_BUNDLE_COUNT_NOT_{REQUIRED_COMPARISONS_PER_CADENCE}"
            )

        for path in files[:REQUIRED_COMPARISONS_PER_CADENCE]:
            try:
                bundle = load_json(path)
                rows = normalize_bundle_rows(bundle)

                if not rows:
                    raise ValueError("no normalized price rows")

                as_of = dt.date.fromisoformat(
                    str(bundle["prediction_identity"]["as_of"])[:10]
                )
                symbol = str(bundle["prediction_identity"]["symbol"])

                run_context = bundle.get("frozen_run_context") or {}
                metadata = run_context.get("run_metadata_json") or {}

                warmup = (
                    metadata.get("authority_warmup_rows")
                    if isinstance(metadata, Mapping)
                    else None
                )
                history_rows = (
                    metadata.get("history_window_rows")
                    if isinstance(metadata, Mapping)
                    else None
                )

                # Exact native M77.19.6 policy defaults if run metadata did not
                # persist the policy values.
                if warmup is None:
                    warmup = 300
                if history_rows is None:
                    history_rows = 750

                first = native.call_profile(
                    service,
                    symbol,
                    rows,
                    as_of,
                    session_set,
                    int(warmup),
                    int(history_rows),
                )
                second = native.call_profile(
                    service,
                    symbol,
                    rows,
                    as_of,
                    session_set,
                    int(warmup),
                    int(history_rows),
                )

                if first is None or second is None:
                    raise ValueError("NOT_ELIGIBLE")

                evidence.append(compare_native(bundle, first, second))

            except Exception as exc:
                errors.append(
                    {
                        "file": str(path.relative_to(root)),
                        "error": type(exc).__name__,
                        "message": str(exc)[:1000],
                    }
                )

        summary = summarize(evidence)

        report["cadences"][cadence] = {
            "bundle_count": len(files),
            "comparisons": len(evidence),
            "error_count": len(errors),
            "errors": errors,
            "summary": summary,
            "evidence": evidence,
        }

        if not summary["pass"]:
            report["blockers"].append(
                f"{cadence}_STRICT_PARITY_NOT_CERTIFIED"
            )

    certified = not report["blockers"]

    report["controlled_exact_input_parity_certified"] = certified
    report["full_23_year_reconstruction_authorized"] = False
    report["production_authority_effect"] = False
    report["next_step"] = (
        "BUILD_M77_19_6_6_LONG_HISTORY_RECONSTRUCTION_AUTHORIZATION_GATE"
        if certified
        else "FORENSIC_REVIEW_M77_19_6_5_2_NATIVE_PARITY_DIFFERENCES"
    )

    out = root / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    )

    print("=== M77.19.6.5.2 NATIVE CONTROLLED EXECUTION & PARITY CERTIFICATION ===")
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("native_runner_sha256_verified: True")
    print("certified_dm_adapter_sha256_verified: True")
    print("parity_thresholds_relaxed: False")

    for cadence in CADENCES:
        c = report["cadences"][cadence]
        print(
            cadence,
            {
                "bundle_count": c["bundle_count"],
                "comparisons": c["comparisons"],
                "error_count": c["error_count"],
                **c["summary"],
            },
        )

    print("controlled_exact_input_parity_certified:", certified)
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")

    if report["blockers"]:
        print("blockers:")
        for blocker in sorted(set(report["blockers"])):
            print(" -", blocker)

    print("next_step:", report["next_step"])
    print("report:", out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
