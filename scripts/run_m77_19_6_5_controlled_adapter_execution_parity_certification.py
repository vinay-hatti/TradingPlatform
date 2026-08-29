#!/usr/bin/env python3
"""
M77.19.6.5 — Controlled Adapter Execution & Strict Parity Certification

Consumes the exact frozen bundles produced by M77.19.6.4.2 and attempts an
actual controlled overlap-period replay through the installed isolated replay
adapter semantics.

This package is deliberately fail closed:
  * it will not guess a replay function when source semantics are ambiguous;
  * it will not use production DB writes;
  * it will not relax any threshold;
  * it will not certify merely because direction is close;
  * it will not authorize the 23-year reconstruction unless strict parity is
    proven for DAILY, WEEKLY, and MONTHLY.

Certification gates:
  direction                100%
  overall_score error      <= 1e-9
  confidence error         <= 1e-9
  semantic state hash      100%
  deterministic repeat     100%
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import importlib.util
import inspect
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping

VERSION = "M77.19.6.5-CONTROLLED-ADAPTER-EXECUTION-PARITY-CERTIFICATION-1.0"

CADENCES = ("DAILY", "WEEKLY", "MONTHLY")
SCORE_EPSILON = 1e-9
CONFIDENCE_EPSILON = 1e-9
DIRECTION_MATCH_REQUIRED_PCT = 100.0
SEMANTIC_HASH_MATCH_REQUIRED_PCT = 100.0
DETERMINISTIC_REPEAT_REQUIRED_PCT = 100.0

NON_SEMANTIC_KEYS = {
    "id", "run_id", "replay_run_id", "snapshot_id", "state_id",
    "publication_id", "request_id", "trace_id", "correlation_id",
    "generated_at", "created_at", "updated_at", "published_at",
    "snapshot_timestamp", "computed_at", "calculated_at", "ingested_at",
    "uuid", "nonce",
}

CANDIDATE_FUNCTION_HINTS = (
    "isolated",
    "historical",
    "replay",
    "adapter",
    "compute",
    "build",
)

REQUIRED_INPUT_HINTS = (
    "history",
    "price_history",
    "bars",
    "as_of",
)

OUTPUT_FIELD_ALIASES = {
    "direction": ("direction", "trend_direction"),
    "overall_score": ("overall_score", "score"),
    "confidence": ("confidence", "confidence_score"),
    "state": ("profile", "state", "payload", "result"),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
    return value


def semantic_projection(value: Any) -> Any:
    if isinstance(value, Mapping):
        out = {}
        for key, item in value.items():
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
            out[str(key)] = semantic_projection(item)
        return out

    if isinstance(value, (list, tuple)):
        return [semantic_projection(x) for x in value]

    return jsonable(value)


def semantic_hash(value: Any) -> str:
    payload = json.dumps(
        semantic_projection(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def require_prior(root: Path, explicit: str | None) -> tuple[Path, dict[str, Any]]:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(
        root / "reports" / "m77_19_6_4_2_joined_frozen_replay_authority_recovery.json"
    )

    for path in candidates:
        if not path.exists():
            continue

        doc = load_json(path)

        if doc.get("exact_frozen_input_context_adapter_ready") is not True:
            raise SystemExit(
                "FAIL CLOSED: M77.19.6.4.2 exact frozen adapter is not READY"
            )

        if doc.get("full_23_year_reconstruction_authorized") is True:
            raise SystemExit(
                "FAIL CLOSED: unexpected prior 23-year authorization"
            )

        if doc.get("production_authority_effect") is True:
            raise SystemExit(
                "FAIL CLOSED: unexpected prior production authority effect"
            )

        if (
            doc.get("next_step")
            != "BUILD_M77_19_6_5_CONTROLLED_ADAPTER_EXECUTION_AND_PARITY_CERTIFICATION"
        ):
            raise SystemExit(
                "FAIL CLOSED: prior report does not authorize M77.19.6.5"
            )

        return path, doc

    raise SystemExit("FAIL CLOSED: M77.19.6.4.2 authority report not found")


def bundle_paths(root: Path, bundle_root: Path) -> dict[str, list[Path]]:
    result = {}
    for cadence in CADENCES:
        path = bundle_root / cadence.lower()
        files = sorted(path.glob("*.json")) if path.exists() else []
        result[cadence] = files
    return result


def verify_bundle(bundle: Mapping[str, Any]) -> list[str]:
    errors = []

    required = (
        "cadence",
        "prediction_identity",
        "frozen_output",
        "frozen_profile",
        "frozen_lineage",
        "frozen_run_context",
        "price_history",
        "price_history_sha256",
        "bundle_semantic_sha256",
    )

    for key in required:
        if key not in bundle:
            errors.append(f"MISSING_{key.upper()}")

    if not bundle.get("price_history"):
        errors.append("EMPTY_PRICE_HISTORY")

    if bundle.get("frozen_profile") is None:
        errors.append("MISSING_FROZEN_PROFILE")

    if bundle.get("frozen_lineage") is None:
        errors.append("MISSING_FROZEN_LINEAGE")

    return errors


def discover_adapter_sources(root: Path) -> list[dict[str, Any]]:
    candidates = []

    bases = [
        root / "scripts",
        root / "src",
        root / "research",
    ]

    for base in bases:
        if not base.exists():
            continue

        for path in base.rglob("*.py"):
            low_path = str(path).lower()

            if not any(
                hint in low_path
                for hint in (
                    "m77",
                    "historical",
                    "replay",
                    "stock_intelligence",
                )
            ):
                continue

            try:
                text = path.read_text(errors="replace")
                tree = ast.parse(text)
            except Exception:
                continue

            for node in tree.body:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue

                name = node.name
                low_name = name.lower()

                if not any(hint in low_name for hint in CANDIDATE_FUNCTION_HINTS):
                    continue

                arg_names = [
                    arg.arg
                    for arg in (
                        list(node.args.posonlyargs)
                        + list(node.args.args)
                        + list(node.args.kwonlyargs)
                    )
                ]

                low_args = {x.lower() for x in arg_names}

                input_score = sum(
                    any(hint in arg for arg in low_args)
                    for hint in REQUIRED_INPUT_HINTS
                )

                cadence_score = sum(
                    cadence.lower() in low_path or cadence.lower() in low_name
                    for cadence in CADENCES
                )

                source_score = 0
                if "19_4_1" in low_path:
                    source_score += 100
                if "isolated" in low_path:
                    source_score += 50
                if "adapter" in low_path:
                    source_score += 30
                if "historical" in low_path:
                    source_score += 20
                if "replay" in low_path:
                    source_score += 20

                score = source_score + input_score * 20 + cadence_score * 10

                candidates.append(
                    {
                        "path": str(path.relative_to(root)),
                        "function": name,
                        "args": arg_names,
                        "score": score,
                    }
                )

    return sorted(
        candidates,
        key=lambda x: (x["score"], x["path"], x["function"]),
        reverse=True,
    )


def cadence_affinity(candidate: Mapping[str, Any], cadence: str) -> int:
    text = (candidate["path"] + " " + candidate["function"]).lower()

    hints = {
        "DAILY": ("daily", "1d"),
        "WEEKLY": ("weekly", "1w"),
        "MONTHLY": ("monthly", "1mo"),
    }[cadence]

    return sum(100 for hint in hints if hint in text)


def choose_adapter(
    candidates: list[Mapping[str, Any]],
    cadence: str,
) -> tuple[Mapping[str, Any] | None, list[Mapping[str, Any]]]:
    ranked = []

    for candidate in candidates:
        score = candidate["score"] + cadence_affinity(candidate, cadence)
        ranked.append((score, candidate))

    ranked.sort(key=lambda x: x[0], reverse=True)

    if not ranked:
        return None, []

    top_score = ranked[0][0]
    top = [candidate for score, candidate in ranked if score == top_score]

    # Scientific fail-closed rule: do not guess if the best adapter is ambiguous.
    if len(top) != 1:
        return None, top

    return top[0], top


def import_function(
    root: Path,
    candidate: Mapping[str, Any],
) -> Callable[..., Any]:
    path = root / candidate["path"]
    module_name = (
        "m77_19_6_5_dynamic_"
        + hashlib.sha256(str(path).encode()).hexdigest()[:12]
    )

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    fn = getattr(module, candidate["function"])
    if not callable(fn):
        raise RuntimeError("Selected adapter symbol is not callable")

    return fn


def find_arg_name(signature: inspect.Signature, aliases: tuple[str, ...]) -> str | None:
    params = {name.lower(): name for name in signature.parameters}

    for alias in aliases:
        if alias.lower() in params:
            return params[alias.lower()]

    return None


def build_call_kwargs(
    fn: Callable[..., Any],
    bundle: Mapping[str, Any],
    cadence: str,
) -> tuple[dict[str, Any], list[str]]:
    sig = inspect.signature(fn)
    kwargs: dict[str, Any] = {}
    blockers = []

    mappings = [
        (
            ("history", "price_history", "bars", "ohlcv", "history_rows"),
            bundle["price_history"],
            "PRICE_HISTORY_ARGUMENT_NOT_FOUND",
        ),
        (
            ("as_of", "as_of_date", "replay_date", "end_date"),
            bundle["prediction_identity"]["as_of"],
            "AS_OF_ARGUMENT_NOT_FOUND",
        ),
        (
            ("symbol", "ticker"),
            bundle["prediction_identity"]["symbol"],
            None,
        ),
        (
            ("cadence", "timeframe", "interval"),
            cadence,
            None,
        ),
        (
            ("external_context", "context"),
            bundle.get("frozen_profile"),
            None,
        ),
        (
            ("profile", "frozen_profile"),
            bundle.get("frozen_profile"),
            None,
        ),
        (
            ("lineage", "frozen_lineage"),
            bundle.get("frozen_lineage"),
            None,
        ),
        (
            ("run_context", "frozen_run_context"),
            bundle.get("frozen_run_context"),
            None,
        ),
    ]

    for aliases, value, required_blocker in mappings:
        arg = find_arg_name(sig, aliases)

        if arg is not None:
            kwargs[arg] = value
        elif required_blocker is not None:
            blockers.append(required_blocker)

    required_without_default = [
        name
        for name, param in sig.parameters.items()
        if param.default is inspect._empty
        and param.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
        and name not in kwargs
    ]

    if required_without_default:
        blockers.append(
            "UNRESOLVED_REQUIRED_ARGUMENTS:"
            + ",".join(sorted(required_without_default))
        )

    return kwargs, blockers


def extract_field(value: Any, aliases: tuple[str, ...]) -> Any:
    if isinstance(value, Mapping):
        low = {str(k).lower(): k for k in value}

        for alias in aliases:
            if alias.lower() in low:
                return value[low[alias.lower()]]

    for alias in aliases:
        if hasattr(value, alias):
            return getattr(value, alias)

    return None


def normalize_output(value: Any) -> dict[str, Any]:
    if hasattr(value, "__dict__") and not isinstance(value, Mapping):
        source = vars(value)
    else:
        source = value

    direction = extract_field(source, OUTPUT_FIELD_ALIASES["direction"])
    score = extract_field(source, OUTPUT_FIELD_ALIASES["overall_score"])
    confidence = extract_field(source, OUTPUT_FIELD_ALIASES["confidence"])

    state = source

    return {
        "direction": jsonable(direction),
        "overall_score": jsonable(score),
        "confidence": jsonable(confidence),
        "state": jsonable(state),
        "semantic_hash": semantic_hash(state),
    }


def execute_once(
    fn: Callable[..., Any],
    bundle: Mapping[str, Any],
    cadence: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    kwargs, blockers = build_call_kwargs(fn, bundle, cadence)

    if blockers:
        return None, blockers

    try:
        result = fn(**kwargs)
    except Exception as exc:
        return None, [f"ADAPTER_EXECUTION_ERROR:{type(exc).__name__}:{exc}"]

    normalized = normalize_output(result)

    if normalized["direction"] is None:
        blockers.append("OUTPUT_DIRECTION_NOT_RECOVERED")

    if normalized["overall_score"] is None:
        blockers.append("OUTPUT_SCORE_NOT_RECOVERED")

    if normalized["confidence"] is None:
        blockers.append("OUTPUT_CONFIDENCE_NOT_RECOVERED")

    if blockers:
        return None, blockers

    return normalized, []


def compare(
    bundle: Mapping[str, Any],
    first: Mapping[str, Any],
    second: Mapping[str, Any],
) -> dict[str, Any]:
    frozen = bundle["frozen_output"]

    score_error = abs(
        float(first["overall_score"]) - float(frozen["overall_score"])
    )
    confidence_error = abs(
        float(first["confidence"]) - float(frozen["confidence"])
    )

    direction_match = str(first["direction"]) == str(frozen["direction"])

    # Compare replay result semantic state against frozen profile semantics.
    frozen_semantic_hash = semantic_hash(bundle["frozen_profile"])
    result_semantic_hash = first["semantic_hash"]

    deterministic_repeat = semantic_hash(first["state"]) == semantic_hash(second["state"])

    return {
        "prediction_id": bundle["prediction_identity"]["prediction_id"],
        "symbol": bundle["prediction_identity"]["symbol"],
        "as_of": bundle["prediction_identity"]["as_of"],
        "frozen_direction": frozen["direction"],
        "replay_direction": first["direction"],
        "direction_match": direction_match,
        "frozen_overall_score": frozen["overall_score"],
        "replay_overall_score": first["overall_score"],
        "score_abs_error": score_error,
        "frozen_confidence": frozen["confidence"],
        "replay_confidence": first["confidence"],
        "confidence_abs_error": confidence_error,
        "frozen_semantic_hash": frozen_semantic_hash,
        "replay_semantic_hash": result_semantic_hash,
        "semantic_hash_match": frozen_semantic_hash == result_semantic_hash,
        "deterministic_repeat": deterministic_repeat,
    }


def summarize(comparisons: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not comparisons:
        return {
            "comparison_count": 0,
            "pass": False,
            "reason": "NO_SUCCESSFUL_COMPARISONS",
        }

    count = len(comparisons)

    direction_pct = (
        100.0 * sum(x["direction_match"] for x in comparisons) / count
    )
    hash_pct = (
        100.0 * sum(x["semantic_hash_match"] for x in comparisons) / count
    )
    repeat_pct = (
        100.0 * sum(x["deterministic_repeat"] for x in comparisons) / count
    )

    max_score_error = max(x["score_abs_error"] for x in comparisons)
    max_confidence_error = max(
        x["confidence_abs_error"] for x in comparisons
    )

    passed = (
        count == 48
        and direction_pct == DIRECTION_MATCH_REQUIRED_PCT
        and max_score_error <= SCORE_EPSILON
        and max_confidence_error <= CONFIDENCE_EPSILON
        and hash_pct == SEMANTIC_HASH_MATCH_REQUIRED_PCT
        and repeat_pct == DETERMINISTIC_REPEAT_REQUIRED_PCT
    )

    return {
        "comparison_count": count,
        "direction_match_pct": direction_pct,
        "max_score_abs_error": max_score_error,
        "max_confidence_abs_error": max_confidence_error,
        "semantic_hash_match_pct": hash_pct,
        "deterministic_repeat_pct": repeat_pct,
        "pass": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--m77-19-6-4-2-report")
    parser.add_argument(
        "--bundle-root",
        default="research_data/m77_19_6_4_2/exact_frozen_input_context_bundles",
    )
    parser.add_argument(
        "--output",
        default="reports/m77_19_6_5_controlled_adapter_execution_parity_certification.json",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()

    prior_path, _ = require_prior(
        root,
        args.m77_19_6_4_2_report,
    )

    bundle_root = root / args.bundle_root
    bundles_by_cadence = bundle_paths(root, bundle_root)

    source_candidates = discover_adapter_sources(root)

    report = {
        "version": VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "prior_report": str(prior_path),
        "governance": {
            "research_only": True,
            "production_database_access_required": False,
            "production_database_writes": False,
            "parity_thresholds_relaxed": False,
            "score_epsilon": SCORE_EPSILON,
            "confidence_epsilon": CONFIDENCE_EPSILON,
            "direction_match_required_pct": DIRECTION_MATCH_REQUIRED_PCT,
            "semantic_hash_match_required_pct": SEMANTIC_HASH_MATCH_REQUIRED_PCT,
            "deterministic_repeat_required_pct": DETERMINISTIC_REPEAT_REQUIRED_PCT,
            "production_authority_effect": False,
            "full_23_year_reconstruction_authorized": False,
        },
        "adapter_source_candidates": source_candidates[:200],
        "cadences": {},
        "blockers": [],
    }

    all_pass = True

    for cadence in CADENCES:
        files = bundles_by_cadence[cadence]

        cadence_result = {
            "bundle_count": len(files),
            "selected_adapter": None,
            "adapter_selection_ambiguity": [],
            "bundle_validation_failures": [],
            "execution_failures": [],
            "comparisons": [],
            "summary": None,
        }

        if len(files) != 48:
            report["blockers"].append(
                f"{cadence}_BUNDLE_COUNT_NOT_48"
            )
            all_pass = False
            report["cadences"][cadence] = cadence_result
            continue

        selected, ambiguity = choose_adapter(source_candidates, cadence)

        if selected is None:
            cadence_result["adapter_selection_ambiguity"] = ambiguity
            report["blockers"].append(
                f"{cadence}_CERTIFIED_ISOLATED_ADAPTER_NOT_UNIQUELY_RESOLVED"
            )
            all_pass = False
            report["cadences"][cadence] = cadence_result
            continue

        cadence_result["selected_adapter"] = selected

        try:
            fn = import_function(root, selected)
        except Exception as exc:
            report["blockers"].append(
                f"{cadence}_ADAPTER_IMPORT_FAILED"
            )
            cadence_result["execution_failures"].append(
                f"{type(exc).__name__}: {exc}"
            )
            all_pass = False
            report["cadences"][cadence] = cadence_result
            continue

        for path in files:
            bundle = load_json(path)
            bundle_errors = verify_bundle(bundle)

            if bundle_errors:
                cadence_result["bundle_validation_failures"].append(
                    {
                        "file": str(path.relative_to(root)),
                        "errors": bundle_errors,
                    }
                )
                continue

            first, errors1 = execute_once(fn, bundle, cadence)

            if errors1:
                cadence_result["execution_failures"].append(
                    {
                        "file": str(path.relative_to(root)),
                        "errors": errors1,
                    }
                )
                continue

            second, errors2 = execute_once(fn, bundle, cadence)

            if errors2:
                cadence_result["execution_failures"].append(
                    {
                        "file": str(path.relative_to(root)),
                        "errors": errors2,
                    }
                )
                continue

            cadence_result["comparisons"].append(
                compare(bundle, first, second)
            )

        cadence_result["summary"] = summarize(
            cadence_result["comparisons"]
        )

        if not cadence_result["summary"]["pass"]:
            all_pass = False
            report["blockers"].append(
                f"{cadence}_STRICT_PARITY_NOT_CERTIFIED"
            )

        report["cadences"][cadence] = cadence_result

    certified = all_pass and not report["blockers"]

    report["controlled_exact_input_parity_certified"] = certified
    report["full_23_year_reconstruction_authorized"] = False
    report["production_authority_effect"] = False

    report["next_step"] = (
        "BUILD_M77_19_6_6_LONG_HISTORY_RECONSTRUCTION_AUTHORIZATION_GATE"
        if certified
        else "RESOLVE_M77_19_6_5_CONTROLLED_EXECUTION_BLOCKERS"
    )

    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    )

    print("=== M77.19.6.5 CONTROLLED ADAPTER EXECUTION & PARITY CERTIFICATION ===")
    print("parity_thresholds_relaxed: False")

    for cadence in CADENCES:
        c = report["cadences"][cadence]
        print(
            cadence,
            {
                "bundle_count": c["bundle_count"],
                "selected_adapter": c["selected_adapter"],
                "execution_failures": len(c["execution_failures"]),
                "summary": c["summary"],
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
    print("report:", output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
