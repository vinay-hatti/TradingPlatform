from __future__ import annotations

import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Callable, Iterable

from .contracts import DealerPositioningPolicy


@dataclass(frozen=True)
class DealerPositionRefreshResult:
    symbol: str
    status: str
    option_snapshot_date: str | None = None
    source_contract_count: int = 0
    executable_contract_count: int = 0
    positioning_label: str | None = None
    confidence_score: float | None = None
    error: str | None = None
    timing: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class DealerPositionRefreshProfile:
    started_at: str
    completed_at: str
    as_of_date: str
    requested_symbols: int
    refreshed_symbols: int
    failed_symbols: int
    skipped_symbols: int
    results: tuple[DealerPositionRefreshResult, ...]
    preload_seconds: float = 0.0
    compute_seconds: float = 0.0
    persistence_seconds: float = 0.0
    report_seconds: float = 0.0
    execution_seconds: float = 0.0
    execution_mode: str = "SEQUENTIAL"
    worker_count: int = 1
    timing_totals: dict[str, float] = field(default_factory=dict)
    timing_max: dict[str, float] = field(default_factory=dict)
    persistence_profile: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class DealerPositionRefreshOrchestrator:
    """Refresh dealer state with immutable preload, pure parallel compute, and one writer.

    M68.2.1.15.8.4 replaces the measured per-symbol PostgreSQL write/commit
    bottleneck with the same architecture that proved successful for option
    valuation: bulk preload -> pure parallel compute -> deterministic bulk
    persistence.  Stage ordering, formulas, current-day replacement semantics,
    and fail-fast behavior remain unchanged.
    """

    def __init__(
        self,
        policy: DealerPositioningPolicy | None = None,
        *,
        output_dir: Path = Path("reports/m44"),
        write_reports: bool = True,
        service_factory: Callable[[DealerPositioningPolicy], object] | None = None,
    ) -> None:
        self.policy = policy or DealerPositioningPolicy()
        self.output_dir = Path(output_dir)
        self.write_reports = write_reports
        self.service_factory = service_factory

    def _preload(self, normalized: tuple[str, ...], as_of: date) -> dict[str, dict]:
        from sqlalchemy import desc, select
        from trading_ai.database.repositories.option_chain import OptionChainRepository
        from trading_ai.database.session import create_session
        from trading_ai.market.models import PriceHistory
        from .database_models import DealerPositionSnapshotModel
        from .serialization import snapshot_from_dict

        preloaded_by_symbol: dict[str, dict] = {}
        with create_session() as session:
            repo = OptionChainRepository(session)
            option_rows = repo.get_range(
                normalized,
                start=as_of - timedelta(days=self.policy.maximum_snapshot_age_days),
                end=as_of,
            )
            source_table = repo.resolved_table_name or "option_contract_history"
            rows_by_symbol_date: dict[str, dict[date, list[dict]]] = defaultdict(lambda: defaultdict(list))
            for row in option_rows:
                rows_by_symbol_date[str(row["symbol"]).upper()][row["quote_date"]].append(row)
            latest_date_by_symbol = {
                symbol: max(by_date) for symbol, by_date in rows_by_symbol_date.items() if by_date
            }

            min_hist_date = min(latest_date_by_symbol.values(), default=as_of) - timedelta(days=90)
            price_rows = session.execute(
                select(PriceHistory.symbol, PriceHistory.date, PriceHistory.close)
                .where(
                    PriceHistory.symbol.in_(normalized),
                    PriceHistory.date >= min_hist_date,
                    PriceHistory.date <= as_of,
                )
                .order_by(PriceHistory.symbol, PriceHistory.date)
            ).all()
            prices_by_symbol: dict[str, list[tuple[date, float]]] = defaultdict(list)
            for symbol, row_date, close in price_rows:
                if close is not None and float(close) > 0:
                    prices_by_symbol[str(symbol).upper()].append((row_date, float(close)))

            previous_rows = session.execute(
                select(DealerPositionSnapshotModel)
                .where(
                    DealerPositionSnapshotModel.symbol.in_(normalized),
                    DealerPositionSnapshotModel.as_of_date < as_of,
                )
                .order_by(
                    DealerPositionSnapshotModel.symbol,
                    desc(DealerPositionSnapshotModel.as_of_date),
                )
            ).scalars().all()
            previous_by_symbol: dict[str, object | None] = {}
            for row in previous_rows:
                if row.symbol in previous_by_symbol:
                    continue
                try:
                    previous_by_symbol[row.symbol] = snapshot_from_dict(json.loads(row.payload_json))
                except Exception:
                    previous_by_symbol[row.symbol] = None

            for symbol in normalized:
                qdate = latest_date_by_symbol.get(symbol)
                if qdate is None:
                    continue
                priced = [(d, c) for d, c in prices_by_symbol.get(symbol, ()) if d <= qdate]
                price_close = priced[-1][1] if priced else None
                history_closes = [c for d, c in priced if d >= qdate - timedelta(days=90)]
                preloaded_by_symbol[symbol] = {
                    "rows": rows_by_symbol_date[symbol][qdate],
                    "quote_date": qdate,
                    "price_close": price_close,
                    "history_closes": history_closes,
                    "previous": previous_by_symbol.get(symbol),
                    "source_table": source_table,
                }
        return preloaded_by_symbol

    def run(
        self,
        symbols: Iterable[str],
        as_of: date,
        *,
        continue_on_error: bool = True,
        max_workers: int = 1,
    ) -> DealerPositionRefreshProfile:
        started = datetime.now(timezone.utc)
        wall_started = perf_counter()
        normalized = tuple(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
        workers = max(1, int(max_workers))

        # Preserve historical/fail-fast/adaptor semantics exactly.  Optimization
        # is enabled only for the normal production multi-symbol refresh.
        optimized = (
            self.service_factory is None
            and continue_on_error
            and workers > 1
            and len(normalized) > 1
        )
        if not optimized:
            return self._run_legacy(normalized, as_of, continue_on_error, workers, started, wall_started)

        from .service import InstitutionalMarketStructureService

        preload_started = perf_counter()
        preloaded = self._preload(normalized, as_of)
        preload_seconds = perf_counter() - preload_started

        snapshots_by_symbol: dict[str, object] = {}

        def compute_one(symbol: str):
            service = InstitutionalMarketStructureService(self.policy)
            started_one = perf_counter()
            try:
                snapshot = service.compute_preloaded(symbol, as_of, preloaded.get(symbol, {}))
                return symbol, snapshot, None, perf_counter() - started_one, dict(getattr(service.engine, "last_profile", {}) or {})
            except ValueError as exc:
                return symbol, None, ("SKIPPED", str(exc)), perf_counter() - started_one, {}
            except Exception as exc:
                return symbol, None, ("FAILED", str(exc)), perf_counter() - started_one, {}

        compute_started = perf_counter()
        with ThreadPoolExecutor(
            max_workers=min(workers, len(normalized)),
            thread_name_prefix="dealer-compute",
        ) as executor:
            computed = list(executor.map(compute_one, normalized))
        compute_seconds = perf_counter() - compute_started

        status_by_symbol: dict[str, tuple[str, str | None]] = {}
        compute_timing: dict[str, float] = {}
        compute_domain_profiles: dict[str, dict[str, float]] = {}
        for symbol, snapshot, error, seconds, domain_profile in computed:
            compute_timing[symbol] = seconds
            compute_domain_profiles[symbol] = domain_profile
            if snapshot is not None:
                snapshots_by_symbol[symbol] = snapshot
                status_by_symbol[symbol] = ("COMPUTED", None)
            else:
                status_by_symbol[symbol] = error or ("FAILED", "Unknown dealer compute failure")

        ordered_snapshots = tuple(
            snapshots_by_symbol[symbol] for symbol in normalized if symbol in snapshots_by_symbol
        )
        persistence_started = perf_counter()
        persistence_profile = InstitutionalMarketStructureService.persist_many(ordered_snapshots)
        persistence_seconds = perf_counter() - persistence_started
        persisted = set(persistence_profile.get("successful_symbols") or ())
        persist_failed = dict(persistence_profile.get("failed_symbols") or {})

        report_started = perf_counter()
        if self.write_reports:
            for symbol in normalized:
                if symbol in persisted:
                    InstitutionalMarketStructureService.write_report(
                        snapshots_by_symbol[symbol], self.output_dir
                    )
        report_seconds = perf_counter() - report_started

        results: list[DealerPositionRefreshResult] = []
        for symbol in normalized:
            snapshot = snapshots_by_symbol.get(symbol)
            if symbol in persisted and snapshot is not None:
                results.append(
                    DealerPositionRefreshResult(
                        symbol=symbol,
                        status="REFRESHED",
                        option_snapshot_date=snapshot.option_snapshot_date,
                        source_contract_count=snapshot.source_contract_count,
                        executable_contract_count=snapshot.executable_contract_count,
                        positioning_label=snapshot.positioning_label,
                        confidence_score=snapshot.confidence_score,
                        timing={"compute_seconds": round(compute_timing.get(symbol, 0.0), 6)},
                    )
                )
            elif symbol in persist_failed:
                results.append(
                    DealerPositionRefreshResult(
                        symbol=symbol,
                        status="FAILED",
                        error=persist_failed[symbol],
                        timing={"compute_seconds": round(compute_timing.get(symbol, 0.0), 6)},
                    )
                )
            else:
                status, error = status_by_symbol.get(symbol, ("FAILED", "No dealer result"))
                results.append(
                    DealerPositionRefreshResult(
                        symbol=symbol,
                        status=status,
                        error=error,
                        timing={"compute_seconds": round(compute_timing.get(symbol, 0.0), 6)},
                    )
                )

        completed = datetime.now(timezone.utc)
        refreshed = sum(r.status == "REFRESHED" for r in results)
        failed = sum(r.status == "FAILED" for r in results)
        skipped = sum(r.status == "SKIPPED" for r in results)
        execution_seconds = perf_counter() - wall_started
        domain_keys = sorted({k for profile in compute_domain_profiles.values() for k in profile})
        timing_totals = {
            "compute_worker_seconds": round(sum(compute_timing.values()), 6),
            "bulk_delete_seconds": float(persistence_profile.get("delete_seconds", 0.0) or 0.0),
            "bulk_prepare_seconds": float(persistence_profile.get("prepare_seconds", 0.0) or 0.0),
            "bulk_insert_seconds": float(persistence_profile.get("insert_seconds", 0.0) or 0.0),
            "bulk_commit_seconds": float(persistence_profile.get("commit_seconds", 0.0) or 0.0),
        }
        for key in domain_keys:
            timing_totals[f"compute_domain_{key}"] = round(sum(float(p.get(key,0.0) or 0.0) for p in compute_domain_profiles.values()), 6)
        timing_max = {
            "compute_seconds": round(max(compute_timing.values(), default=0.0), 6),
        }
        for key in domain_keys:
            timing_max[f"compute_domain_{key}"] = round(max((float(p.get(key,0.0) or 0.0) for p in compute_domain_profiles.values()), default=0.0), 6)
        return DealerPositionRefreshProfile(
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
            as_of_date=as_of.isoformat(),
            requested_symbols=len(normalized),
            refreshed_symbols=refreshed,
            failed_symbols=failed,
            skipped_symbols=skipped,
            results=tuple(results),
            preload_seconds=round(preload_seconds, 6),
            compute_seconds=round(compute_seconds, 6),
            persistence_seconds=round(persistence_seconds, 6),
            report_seconds=round(report_seconds, 6),
            execution_seconds=round(execution_seconds, 6),
            execution_mode="PARALLEL_PURE_COMPUTE_SINGLE_BULK_WRITER",
            worker_count=min(workers, len(normalized)),
            timing_totals=timing_totals,
            timing_max=timing_max,
            persistence_profile=dict(persistence_profile),
        )

    def _run_legacy(
        self,
        normalized: tuple[str, ...],
        as_of: date,
        continue_on_error: bool,
        workers: int,
        started: datetime,
        wall_started: float,
    ) -> DealerPositionRefreshProfile:
        def refresh_one(symbol: str) -> DealerPositionRefreshResult:
            if self.service_factory is None:
                from .service import InstitutionalMarketStructureService
                service = InstitutionalMarketStructureService(self.policy)
            else:
                service = self.service_factory(self.policy)
            try:
                kwargs = {
                    "output_dir": self.output_dir,
                    "persist": True,
                    "write_reports": self.write_reports,
                }
                if self.service_factory is None:
                    kwargs["preloaded"] = None
                snapshot = service.run(symbol, as_of, **kwargs)
                timing = dict(getattr(service, "last_profile", {}) or {})
                return DealerPositionRefreshResult(
                    symbol=symbol,
                    status="REFRESHED",
                    option_snapshot_date=snapshot.option_snapshot_date,
                    source_contract_count=snapshot.source_contract_count,
                    executable_contract_count=snapshot.executable_contract_count,
                    positioning_label=snapshot.positioning_label,
                    confidence_score=snapshot.confidence_score,
                    timing={k: float(v) for k, v in timing.items() if isinstance(v, (int, float))},
                )
            except ValueError as exc:
                if not continue_on_error:
                    raise
                return DealerPositionRefreshResult(symbol=symbol, status="SKIPPED", error=str(exc))
            except Exception as exc:
                if not continue_on_error:
                    raise
                return DealerPositionRefreshResult(symbol=symbol, status="FAILED", error=str(exc))

        if workers <= 1 or len(normalized) <= 1 or not continue_on_error:
            execution_mode = "SEQUENTIAL"
            results = [refresh_one(symbol) for symbol in normalized]
        else:
            execution_mode = "PARALLEL_SYMBOL_ISOLATED_PROFILED"
            with ThreadPoolExecutor(
                max_workers=min(workers, len(normalized)), thread_name_prefix="dealer-positioning"
            ) as executor:
                results = list(executor.map(refresh_one, normalized))

        timing_keys = sorted({key for result in results for key in result.timing})
        timing_totals = {
            key: round(sum(result.timing.get(key, 0.0) for result in results), 6)
            for key in timing_keys
        }
        timing_max = {
            key: round(max((result.timing.get(key, 0.0) for result in results), default=0.0), 6)
            for key in timing_keys
        }
        completed = datetime.now(timezone.utc)
        return DealerPositionRefreshProfile(
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
            as_of_date=as_of.isoformat(),
            requested_symbols=len(normalized),
            refreshed_symbols=sum(r.status == "REFRESHED" for r in results),
            failed_symbols=sum(r.status == "FAILED" for r in results),
            skipped_symbols=sum(r.status == "SKIPPED" for r in results),
            results=tuple(results),
            execution_seconds=round(perf_counter() - wall_started, 6),
            execution_mode=execution_mode,
            worker_count=min(workers, len(normalized)) if normalized else 0,
            timing_totals=timing_totals,
            timing_max=timing_max,
        )


def write_refresh_profile(profile: DealerPositionRefreshProfile, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(profile.to_dict(), indent=2, allow_nan=False), encoding="utf-8")
    temp.replace(target)
    return target
