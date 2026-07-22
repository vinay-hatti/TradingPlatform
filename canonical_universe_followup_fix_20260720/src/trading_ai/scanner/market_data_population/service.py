from __future__ import annotations

import csv
import json
import time
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from .models import MarketDataCoverage, MarketDataPopulationResult, SymbolPopulationResult
from .policy import MarketDataPopulationPolicy
from .repository import PriceHistoryBulkRepository
from .resource_lifecycle import assert_fd_headroom, collect_resources, snapshot_resources
from .serialization import file_sha256, write_failures_csv, write_json_atomic
from trading_ai.universe import CanonicalUniverse


class BulkMarketDataPopulationService:
    def __init__(self, provider, policy: MarketDataPopulationPolicy | None = None) -> None:
        self.provider = provider
        self.policy = policy or MarketDataPopulationPolicy()
        self.policy.validate()

    @staticmethod
    def load_symbols(universe_csv: str | Path) -> tuple[str, ...]:
        return CanonicalUniverse(Path(universe_csv)).symbols()

    @staticmethod
    def _preflight_failure_category(symbol: str) -> str:
        upper = symbol.upper()
        warrant_markers = ('.W', '-W', '/W', '.WS', '-WS', '/WS')
        right_markers = ('.R', '-R', '/R')
        unit_markers = ('.U', '-U', '/U')
        if upper.endswith(warrant_markers):
            return 'UNSUPPORTED_WARRANT'
        if upper.endswith(right_markers):
            return 'UNSUPPORTED_RIGHT'
        if upper.endswith(unit_markers):
            return 'UNSUPPORTED_UNIT'
        if any(char.isspace() for char in upper) or not upper:
            return 'INVALID_SYMBOL'
        return ''

    @staticmethod
    def _provider_failure_category(message: str) -> str:
        lowered = message.lower()
        if 'too many open files' in lowered:
            return 'RESOURCE_EXHAUSTED'
        if 'unable to open database file' in lowered or 'operationalerror' in lowered:
            return 'PROVIDER_CACHE_ERROR'
        if 'timezone' in lowered:
            return 'NO_TIMEZONE'
        if 'delisted' in lowered:
            return 'POSSIBLY_DELISTED'
        if 'no price' in lowered or 'no data' in lowered:
            return 'NO_PRICE_DATA'
        if 'timeout' in lowered:
            return 'PROVIDER_TIMEOUT'
        return 'PROVIDER_ERROR'

    def run(
        self,
        *,
        session,
        universe_csv: str | Path,
        report_dir: str | Path = 'reports/m35/phase1/market_data_population',
        resume: bool = False,
        force_refresh: bool = False,
        start: date | None = None,
        end: date | None = None,
        limit: int | None = None,
    ) -> MarketDataPopulationResult:
        started = datetime.now(timezone.utc)
        run_id = f"m35p1s4c1-{started.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
        report_dir = Path(report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = report_dir / 'checkpoint.json'

        canonical_universe = CanonicalUniverse(Path(universe_csv))
        symbols = canonical_universe.symbols()
        if limit is not None:
            symbols = symbols[:max(0, limit)]
        provider_symbol_map = canonical_universe.provider_symbol_map()
        end_date = end or date.today()
        start_date = start or (end_date - timedelta(days=self.policy.lookback_days))

        repository = PriceHistoryBulkRepository(session)
        existing = repository.coverage(symbols)
        stale_cutoff = end_date - timedelta(days=self.policy.stale_after_days)
        fresh = {
            symbol for symbol, (count, latest) in existing.items()
            if count >= self.policy.minimum_bars and latest is not None and latest >= stale_cutoff
        }

        processed: set[str] = set()
        completed: set[str] = set()
        if resume and checkpoint_path.is_file():
            try:
                checkpoint = json.loads(checkpoint_path.read_text(encoding='utf-8'))
                processed = set(checkpoint.get('processed_symbols', checkpoint.get('completed_symbols', [])))
                completed = set(checkpoint.get('completed_symbols', []))
            except (OSError, ValueError, TypeError):
                processed = set()
                completed = set()

        candidates = [symbol for symbol in symbols if force_refresh or symbol not in fresh]
        pending = [symbol for symbol in candidates if symbol not in processed]
        results: list[SymbolPopulationResult] = []
        rows_upserted = 0
        resource_samples: list[dict] = [snapshot_resources().to_dict()]

        # Reject clearly unsupported exchange instruments before invoking yfinance.
        fetchable: list[str] = []
        for symbol in pending:
            category = self._preflight_failure_category(symbol)
            if category:
                results.append(SymbolPopulationResult(
                    symbol=symbol,
                    status='SKIPPED',
                    attempts=0,
                    message='Instrument type is outside the equity/ETF OHLCV population scope',
                    failure_category=category,
                ))
                processed.add(symbol)
            else:
                fetchable.append(symbol)

        for offset in range(0, len(fetchable), self.policy.batch_size):
            assert_fd_headroom(self.policy.minimum_fd_headroom)
            batch = fetchable[offset:offset + self.policy.batch_size]
            provider_batch = tuple(provider_symbol_map.get(symbol, symbol) for symbol in batch)
            canonical_by_provider = {provider_symbol_map.get(symbol, symbol): symbol for symbol in batch}
            batch_data = None
            last_error: Exception | None = None
            attempts = 0

            for attempt in range(1, self.policy.max_retries + 2):
                attempts = attempt
                try:
                    batch_data = self.provider.fetch_batch(provider_batch, start_date, end_date + timedelta(days=1))
                    break
                except Exception as exc:  # provider boundary: isolate and report
                    last_error = exc
                    if attempt > self.policy.max_retries:
                        break
                    if self.policy.collect_resources_each_batch:
                        resource_samples.append(collect_resources().to_dict())
                    time.sleep(self.policy.retry_backoff_seconds * attempt)

            if batch_data is None:
                message = f'{type(last_error).__name__}: {last_error}' if last_error else 'Provider returned no batch'
                category = self._provider_failure_category(message)
                results.extend(SymbolPopulationResult(
                    symbol=symbol,
                    status='FAILED',
                    attempts=attempts,
                    message=message,
                    failure_category=category,
                ) for symbol in batch)
                processed.update(batch)
                if not self.policy.continue_on_error:
                    break
            else:
                try:
                    for symbol in batch:
                        provider_symbol = provider_symbol_map.get(symbol, symbol)
                        provider_bars = tuple(batch_data.get(provider_symbol, ()))
                        bars = tuple(
                            bar if bar.symbol == symbol else replace(bar, symbol=symbol)
                            for bar in provider_bars
                        )
                        processed.add(symbol)
                        if not bars:
                            results.append(SymbolPopulationResult(
                                symbol=symbol,
                                status='FAILED',
                                attempts=attempts,
                                message='No price bars returned; symbol may be unsupported, inactive, or delisted',
                                failure_category='NO_PRICE_DATA',
                            ))
                            continue
                        count = repository.upsert(bars)
                        rows_upserted += count
                        results.append(SymbolPopulationResult(
                            symbol=symbol,
                            status='READY',
                            rows_received=len(bars),
                            rows_upserted=count,
                            attempts=attempts,
                            first_date=bars[0].date,
                            last_date=bars[-1].date,
                        ))
                        completed.add(symbol)
                finally:
                    batch_data.clear()
                    del batch_data

            resource_snapshot = collect_resources() if self.policy.collect_resources_each_batch else snapshot_resources()
            resource_samples.append(resource_snapshot.to_dict())
            write_json_atomic(checkpoint_path, {
                'schema_version': 'm35.phase1.step4c1.checkpoint.v1',
                'run_id': run_id,
                'processed_symbols': sorted(processed),
                'completed_symbols': sorted(completed),
                'updated_at': datetime.now(timezone.utc),
                'start': start_date,
                'end': end_date,
                'last_batch_offset': offset,
                'last_batch_size': len(batch),
                'resource_snapshot': resource_snapshot,
            })
            if self.policy.request_pause_seconds:
                time.sleep(self.policy.request_pause_seconds)

        coverage_rows = repository.coverage(symbols)
        covered = stale = insufficient = 0
        for symbol in symbols:
            count, latest = coverage_rows.get(symbol, (0, None))
            if count < self.policy.minimum_bars:
                insufficient += 1
            elif latest is None or latest < stale_cutoff:
                stale += 1
            else:
                covered += 1
        missing = sum(1 for symbol in symbols if symbol not in coverage_rows)
        pct = (covered / len(symbols) * 100.0) if symbols else 0.0
        coverage_status = 'READY' if pct >= self.policy.minimum_coverage_pct else ('DEGRADED' if covered else 'FAILED')
        coverage = MarketDataCoverage(
            len(symbols), covered, stale, insufficient, missing, pct,
            self.policy.minimum_coverage_pct, coverage_status,
        )

        failed = sum(item.status == 'FAILED' for item in results)
        skipped = sum(item.status == 'SKIPPED' for item in results)
        succeeded = sum(item.status == 'READY' for item in results)
        status = coverage_status if failed == 0 else ('DEGRADED' if covered else 'FAILED')
        warnings: list[str] = []
        if failed:
            warnings.append(f'{failed} symbols failed or returned no data')
        if skipped:
            warnings.append(f'{skipped} unsupported instruments were skipped before provider download')
        if coverage_status != 'READY':
            warnings.append(f'Coverage {pct:.2f}% is below required {self.policy.minimum_coverage_pct:.2f}%')

        completed_at = datetime.now(timezone.utc)
        result = MarketDataPopulationResult(
            run_id, started, completed_at, status, len(symbols), len(pending),
            succeeded, failed + skipped, len(fresh), rows_upserted, coverage,
            tuple(results), tuple(warnings), checkpoint_path=str(checkpoint_path),
            report_dir=str(report_dir),
        )
        write_json_atomic(report_dir / 'population_summary.json', result.to_dict())
        write_json_atomic(report_dir / 'coverage_report.json', coverage.to_dict())
        write_failures_csv(report_dir / 'failed_symbols.csv', results)
        write_json_atomic(report_dir / 'resource_health.json', {
            'schema_version': 'm35.phase1.step4c1.resources.v1',
            'samples': resource_samples,
            'final': snapshot_resources(),
        })
        write_json_atomic(report_dir / 'population_manifest.json', {
            'schema_version': 'm35.phase1.step4c1.v1',
            'run_id': run_id,
            'provider': self.provider.name,
            'universe_csv': str(universe_csv),
            'universe_sha256': file_sha256(universe_csv),
            'policy': self.policy,
            'result': result.to_dict(),
        })
        return result
