from __future__ import annotations

import argparse
import inspect
import json
import sys
from dataclasses import is_dataclass, replace
from pathlib import Path
from typing import Any, Sequence, get_args, get_origin

from .ranking_contracts import RankingQuery
from .ranking_loader import discover_ranking_files, discover_symbol_data_files, load_ranking_records
from .ranking_service import OpportunityRankingService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Milestone 35 Phase 5 Step 3 opportunity rankings view model")
    parser.add_argument("--rankings-json", type=Path)
    parser.add_argument("--top-n", type=int, choices=(10, 25, 50, 100), default=50)
    parser.add_argument("--page-size", type=int, default=25)
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--search", default="")
    parser.add_argument("--sort-field", default="institutional_score")
    parser.add_argument("--sort-direction", choices=("ASC", "DESC"), default="DESC")
    parser.add_argument("--select-symbol")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/m35/phase5/dashboard"))
    parser.add_argument("--list-ranking-files", action="store_true")
    parser.add_argument("--list-data-files", action="store_true")
    return parser


def _supported_parameter(signature: inspect.Signature, *names: str) -> str | None:
    for name in names:
        if name in signature.parameters:
            return name
    return None


def _enum_value(annotation: Any, raw: str) -> Any:
    candidates = [annotation]
    origin = get_origin(annotation)
    if origin is not None:
        candidates.extend(get_args(annotation))
    for candidate in candidates:
        try:
            if isinstance(candidate, type) and hasattr(candidate, "__members__"):
                return candidate(raw)
        except (TypeError, ValueError):
            pass
    return raw


def _build_query(args: argparse.Namespace) -> RankingQuery:
    signature = inspect.signature(RankingQuery)
    kwargs: dict[str, Any] = {}
    mappings = (
        (("top_n", "limit"), args.top_n),
        (("page", "page_number"), args.page),
        (("page_size", "per_page"), args.page_size),
        (("search", "search_text", "query", "query_text"), args.search),
        (("sort_field", "order_by"), args.sort_field),
        (("selected_symbol", "selected_candidate", "candidate_symbol"), args.select_symbol.upper() if args.select_symbol else None),
    )
    for aliases, value in mappings:
        name = _supported_parameter(signature, *aliases)
        if name is not None:
            kwargs[name] = value
    direction_name = _supported_parameter(signature, "sort_direction", "direction", "order_direction")
    if direction_name is not None:
        kwargs[direction_name] = _enum_value(signature.parameters[direction_name].annotation, args.sort_direction)
    return RankingQuery(**kwargs)


def _call_method(method: Any, rankings: list[Any], query: RankingQuery) -> Any:
    signature = inspect.signature(method)
    kwargs: dict[str, Any] = {}
    rankings_name = _supported_parameter(signature, "rankings", "records", "opportunities", "candidates", "items")
    query_name = _supported_parameter(signature, "query", "ranking_query", "request", "view_query")
    if rankings_name is not None:
        kwargs[rankings_name] = rankings
    if query_name is not None:
        kwargs[query_name] = query
    if kwargs:
        return method(**kwargs)
    required = [p for p in signature.parameters.values() if p.default is inspect._empty and p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    if len(required) >= 2:
        return method(rankings, query)
    if len(required) == 1:
        return method(query if "query" in required[0].name.lower() else rankings)
    return method()


def _invoke_service(service: OpportunityRankingService, rankings: list[Any], query: RankingQuery) -> Any:
    for name in ("build_and_persist", "build_view_and_persist", "create_and_persist", "generate_and_persist", "build_view", "run", "build", "create_view", "generate", "evaluate"):
        method = getattr(service, name, None)
        if callable(method):
            try:
                return _call_method(method, rankings, query)
            except TypeError:
                continue
    raise AttributeError("No compatible opportunity ranking service method was found")


def _view_value(view: Any, *names: str, default: Any = None) -> Any:
    if isinstance(view, dict):
        for name in names:
            if view.get(name) is not None:
                return view[name]
        nested = view.get("view")
        return _view_value(nested, *names, default=default) if nested is not None else default
    for name in names:
        if hasattr(view, name):
            value = getattr(view, name)
            if value is not None:
                return value
    return default


def _candidate_symbol(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.upper()
    if isinstance(value, dict):
        raw = value.get("symbol") or value.get("ticker") or value.get("selected_symbol")
        return str(raw).upper() if raw else None
    for name in ("symbol", "ticker", "selected_symbol"):
        raw = getattr(value, name, None)
        if raw:
            return str(raw).upper()
    return None


def _set_selected_symbol(view: Any, symbol: str) -> Any:
    symbol = symbol.upper()
    if isinstance(view, dict):
        updated = dict(view)
        updated["selected_symbol"] = symbol
        return updated
    if is_dataclass(view):
        fields = getattr(view, "__dataclass_fields__", {})
        for field_name in ("selected_symbol", "selected_candidate", "candidate_symbol"):
            if field_name in fields:
                try:
                    return replace(view, **{field_name: symbol})
                except TypeError:
                    pass
    for name in ("selected_symbol", "selected_candidate", "candidate_symbol"):
        if hasattr(view, name):
            try:
                setattr(view, name, symbol)
                return view
            except (AttributeError, TypeError):
                pass
    return {
        "view": view,
        "selected_symbol": symbol,
        "total_records": _view_value(view, "total_records", "total"),
        "filtered_records": _view_value(view, "filtered_records", "filtered_total"),
        "page": _view_value(view, "page", "page_number"),
        "page_size": _view_value(view, "page_size", "per_page"),
        "page_count": _view_value(view, "page_count", "total_pages"),
    }


def _apply_selection(service: OpportunityRankingService, view: Any, selected_symbol: str | None) -> Any:
    if not selected_symbol:
        return view
    requested = selected_symbol.upper()
    method = getattr(service, "select_candidate", None)
    result = None
    if callable(method):
        signature = inspect.signature(method)
        kwargs: dict[str, Any] = {}
        view_name = _supported_parameter(signature, "view", "ranking_view", "model")
        symbol_name = _supported_parameter(signature, "symbol", "selected_symbol", "candidate_symbol")
        if view_name is not None:
            kwargs[view_name] = view
        if symbol_name is not None:
            kwargs[symbol_name] = requested
        try:
            if kwargs:
                result = method(**kwargs)
            else:
                required = [p for p in signature.parameters.values() if p.default is inspect._empty]
                result = method(view, requested) if len(required) >= 2 else method(requested)
        except TypeError:
            result = None
    return _set_selected_symbol(view, _candidate_symbol(result) or requested)


def _persist_if_supported(service: OpportunityRankingService, view: Any) -> Any:
    for name in ("persist", "save", "write_outputs", "serialize"):
        method = getattr(service, name, None)
        if not callable(method):
            continue
        signature = inspect.signature(method)
        view_name = _supported_parameter(signature, "view", "ranking_view", "model", "result")
        try:
            result = method(**{view_name: view}) if view_name else method(view)
            if result is None or isinstance(result, (str, Path)):
                return view
            if _view_value(result, "total_records", "total") is None:
                return view
            return result
        except TypeError:
            continue
    return view


def _print_data_files() -> int:
    candidates = discover_symbol_data_files()
    if not candidates:
        print("No symbol-bearing JSON files found under reports/.")
        return 1
    for candidate in candidates:
        print(f"{candidate.path}\trecords={candidate.record_count}\tquality={candidate.quality_score}")
    return 0


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_ranking_files:
        files = discover_ranking_files()
        for path in files:
            print(path)
        return 0 if files else 1
    if args.list_data_files:
        return _print_data_files()
    try:
        resolved_path, rankings = load_ranking_records(args.rankings_json)
        service = OpportunityRankingService(output_dir=args.output_dir)
        view = _invoke_service(service, rankings, _build_query(args))
        view = _apply_selection(service, view, args.select_symbol)
        view = _persist_if_supported(service, view)
    except (FileNotFoundError, ValueError, TypeError, AttributeError) as exc:
        print(f"Opportunity rankings could not be generated: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "rankings_input": str(resolved_path),
        "total_records": _view_value(view, "total_records", "total", default=len(rankings)),
        "filtered_records": _view_value(view, "filtered_records", "filtered_total", default=len(rankings)),
        "page": _view_value(view, "page", "page_number", default=args.page),
        "page_size": _view_value(view, "page_size", "per_page", default=args.page_size),
        "page_count": _view_value(view, "page_count", "total_pages"),
        "selected_symbol": _view_value(view, "selected_symbol", "selected_candidate", "candidate_symbol", default=args.select_symbol.upper() if args.select_symbol else None),
        "output_dir": str(args.output_dir),
    }, indent=2, default=str))
    return 0
