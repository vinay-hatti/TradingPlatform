from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from .filter_contracts import SavedScannerView, ScannerFilter
from .filter_service import ScannerFilterService
from .ranking_loader import load_ranking_records
from .saved_view_repository import SavedScannerViewRepository
from .saved_view_service import SavedScannerViewService


def _csv_tuple(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(
        item.strip()
        for item in value.split(",")
        if item.strip()
    )


def _add_filter_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--min-institutional-score", type=float)
    parser.add_argument("--max-institutional-score", type=float)
    parser.add_argument("--min-probability-of-profit", type=float)
    parser.add_argument("--max-probability-of-profit", type=float)
    parser.add_argument("--min-liquidity-score", type=float)
    parser.add_argument("--min-open-interest", type=int)
    parser.add_argument("--min-volume", type=int)
    parser.add_argument("--max-spread-pct", type=float)
    parser.add_argument("--sectors")
    parser.add_argument("--directions")
    parser.add_argument("--strategy-types")
    parser.add_argument("--symbols")
    parser.add_argument("--exclude-symbols")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Milestone 35 Phase 5 Step 4 scanner filters and saved views"
        )
    )
    parser.add_argument(
        "--saved-views-json",
        type=Path,
        default=Path(
            "reports/m35/phase5/dashboard/saved_views.json"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--rankings-json", type=Path, required=True)
    apply_parser.add_argument("--saved-view")
    apply_parser.add_argument("--output-json", type=Path)
    _add_filter_arguments(apply_parser)

    save_parser = subparsers.add_parser("save")
    save_parser.add_argument("--name", required=True)
    save_parser.add_argument("--description", default="")
    save_parser.add_argument("--sort-field", default="institutional_score")
    save_parser.add_argument(
        "--sort-direction",
        choices=("ASC", "DESC"),
        default="DESC",
    )
    save_parser.add_argument("--top-n", type=int, default=50)
    save_parser.add_argument("--page-size", type=int, default=25)
    _add_filter_arguments(save_parser)

    subparsers.add_parser("list")

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("--name", required=True)

    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument("--name", required=True)

    return parser


def _filters_from_args(args: argparse.Namespace) -> ScannerFilter:
    return ScannerFilter(
        min_institutional_score=getattr(
            args, "min_institutional_score", None
        ),
        max_institutional_score=getattr(
            args, "max_institutional_score", None
        ),
        min_probability_of_profit=getattr(
            args, "min_probability_of_profit", None
        ),
        max_probability_of_profit=getattr(
            args, "max_probability_of_profit", None
        ),
        min_liquidity_score=getattr(
            args, "min_liquidity_score", None
        ),
        min_open_interest=getattr(args, "min_open_interest", None),
        min_volume=getattr(args, "min_volume", None),
        max_spread_pct=getattr(args, "max_spread_pct", None),
        sectors=_csv_tuple(getattr(args, "sectors", None)),
        directions=_csv_tuple(getattr(args, "directions", None)),
        strategy_types=_csv_tuple(
            getattr(args, "strategy_types", None)
        ),
        symbols=_csv_tuple(getattr(args, "symbols", None)),
        exclude_symbols=_csv_tuple(
            getattr(args, "exclude_symbols", None)
        ),
    )


def _looks_like_record(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    keys = {str(key).lower() for key in value}
    return bool(
        keys
        & {
            "symbol",
            "ticker",
            "underlying_symbol",
            "institutional_score",
            "score",
            "ranking_score",
            "probability_of_profit",
            "direction",
            "signal",
            "strategy",
            "strategy_type",
        }
    )


def _extract_raw_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        direct = [item for item in payload if isinstance(item, dict)]
        if direct:
            return direct
        return []

    if not isinstance(payload, dict):
        return []

    preferred_keys = (
        "records",
        "rankings",
        "opportunities",
        "candidates",
        "live_trade_candidates",
        "recommendations",
        "results",
        "items",
        "data",
    )
    for key in preferred_keys:
        value = payload.get(key)
        if isinstance(value, list):
            records = [item for item in value if isinstance(item, dict)]
            if records:
                return records

    if _looks_like_record(payload):
        return [payload]

    discovered: list[dict[str, Any]] = []
    for value in payload.values():
        if isinstance(value, list):
            discovered.extend(
                item
                for item in value
                if isinstance(item, dict) and _looks_like_record(item)
            )
        elif isinstance(value, dict):
            discovered.extend(_extract_raw_records(value))
    return discovered


def _load_filter_records(path: Path) -> tuple[Path, list[Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Ranking input does not exist: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return load_ranking_records(path)

    raw_records = _extract_raw_records(payload)
    if raw_records:
        return path, raw_records

    # Backward-compatible fallback for Step 3 ranking snapshots and older
    # serialized dashboard contracts.
    return load_ranking_records(path)


def _record_payload(record: Any) -> Any:
    if isinstance(record, dict):
        return record
    if hasattr(record, "model_dump"):
        return record.model_dump()
    if hasattr(record, "dict"):
        return record.dict()
    if hasattr(record, "__dict__"):
        return {
            key: value
            for key, value in vars(record).items()
            if not key.startswith("_")
        }
    return str(record)


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository = SavedScannerViewRepository(args.saved_views_json)
    saved_views = SavedScannerViewService(repository)

    if args.command == "list":
        payload = [view.to_dict() for view in saved_views.list_views()]
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "show":
        print(json.dumps(saved_views.load(args.name).to_dict(), indent=2))
        return 0

    if args.command == "delete":
        deleted = saved_views.delete(args.name)
        print(
            json.dumps(
                {"name": args.name, "deleted": deleted},
                indent=2,
            )
        )
        return 0 if deleted else 1

    if args.command == "save":
        view = SavedScannerView(
            name=args.name,
            description=args.description,
            filters=_filters_from_args(args),
            sort_field=args.sort_field,
            sort_direction=args.sort_direction,
            top_n=args.top_n,
            page_size=args.page_size,
        )
        saved_views.save(view)
        print(json.dumps(view.to_dict(), indent=2))
        return 0

    if args.command == "apply":
        resolved_path, records = _load_filter_records(args.rankings_json)
        if args.saved_view:
            filters = saved_views.load(args.saved_view).filters
        else:
            filters = _filters_from_args(args)

        filtered = ScannerFilterService().apply(records, filters)
        payload = {
            "rankings_input": str(resolved_path),
            "input_records": len(records),
            "filtered_records": len(filtered),
            "filters": filters.to_dict(),
            "records": [_record_payload(record) for record in filtered],
        }

        if args.output_json:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(
                json.dumps(payload, indent=2, default=str) + "\n",
                encoding="utf-8",
            )

        print(
            json.dumps(
                {
                    "rankings_input": str(resolved_path),
                    "input_records": len(records),
                    "filtered_records": len(filtered),
                    "output_json": (
                        str(args.output_json)
                        if args.output_json
                        else None
                    ),
                },
                indent=2,
            )
        )
        return 0

    raise RuntimeError(f"Unsupported command: {args.command}")
