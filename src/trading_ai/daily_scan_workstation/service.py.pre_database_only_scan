from __future__ import annotations

import json
import subprocess
import sys
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from .models import DataRefreshRequest, DailyScanRequest, RefreshMode, RunKind, RunStatus, ScannerRun


class DailyScanWorkstationService:
    def __init__(self, repository_root: Path, artifact_root: Path):
        self.repository_root = repository_root.resolve()
        self.run_root = (artifact_root / "m43" / "runs").resolve()
        self.run_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}

    def _path(self, run_id: str) -> Path:
        return self.run_root / f"{run_id}.json"

    def _save(self, run: ScannerRun) -> None:
        with self._lock:
            path = self._path(run.run_id)
            temp = path.with_suffix(".tmp")
            temp.write_text(run.model_dump_json(indent=2), encoding="utf-8")
            temp.replace(path)

    def get(self, run_id: str) -> ScannerRun:
        path = self._path(run_id)
        if not path.exists():
            raise KeyError(run_id)
        return ScannerRun.model_validate_json(path.read_text(encoding="utf-8"))

    def list_runs(self, limit: int = 50) -> list[ScannerRun]:
        runs: list[ScannerRun] = []
        for path in self.run_root.glob("*.json"):
            try:
                runs.append(ScannerRun.model_validate_json(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return sorted(runs, key=lambda item: item.created_at, reverse=True)[:limit]

    def _active(self, kind: RunKind) -> ScannerRun | None:
        return next((run for run in self.list_runs(100) if run.kind == kind and run.status in {RunStatus.QUEUED, RunStatus.RUNNING}), None)

    def start_refresh(self, payload: DataRefreshRequest, requested_by: str) -> ScannerRun:
        if active := self._active(RunKind.DATA_REFRESH):
            return active
        args = [
            "scripts/run_m43_market_ingestion_workflow.py",
            "--data-scope", payload.data_scope,
            "--refresh-mode", payload.refresh_mode.value,
            "--universe", payload.universe,
            "--start", payload.start.isoformat(),
            "--end", payload.end.isoformat(),
            "--minimum-bars", str(payload.minimum_bars),
            "--stale-after-days", str(payload.stale_after_days),
            "--minimum-coverage-pct", str(payload.minimum_coverage_pct),
            "--maximum-failed-symbols", str(payload.maximum_failed_symbols),
            "--max-retries", str(payload.max_retries),
            "--retry-backoff-seconds", str(payload.retry_backoff_seconds),
            "--maximum-retry-backoff-seconds", str(payload.maximum_retry_backoff_seconds),
            "--retry-jitter-ratio", str(payload.retry_jitter_ratio),
            "--rate-limit-cooldown-seconds", str(payload.rate_limit_cooldown_seconds),
            "--circuit-breaker-threshold", str(payload.circuit_breaker_threshold),
            "--circuit-breaker-cooldown-seconds", str(payload.circuit_breaker_cooldown_seconds),
            "--batch-size", str(payload.batch_size),
        ]
        args.append("--continue-on-degraded" if payload.continue_on_degraded_refresh else "--block-on-degraded")
        symbols = [symbol.strip().upper() for symbol in payload.symbols if symbol.strip()]
        if symbols:
            args += ["--symbols", ",".join(dict.fromkeys(symbols))]
        return self._start(RunKind.DATA_REFRESH, payload.model_dump(mode="json"), args, requested_by, None)

    def start_scan(self, payload: DailyScanRequest, requested_by: str) -> ScannerRun:
        if active := self._active(RunKind.DAILY_SCAN):
            return active
        report_date = date.today().isoformat()
        args = [
            "scripts/run_m43_daily_scan_workflow.py",
            "--refresh-mode", payload.refresh_mode.value,
            "--universe", payload.universe,
            "--start", payload.start.isoformat(),
            "--end", payload.end.isoformat(),
            "--min-score", str(payload.minimum_score),
            "--top", str(payload.top),
            "--pricing-dte", str(payload.pricing_dte),
            "--expiration-mode", payload.expiration_mode,
            "--minimum-dte", str(payload.minimum_dte),
            "--maximum-dte", str(payload.maximum_dte),
            "--maximum-expirations-per-symbol", str(payload.maximum_expirations_per_symbol),
            "--maximum-trades-per-expiration", str(payload.maximum_trades_per_expiration),
            "--option-data-mode", payload.option_data_mode,
            "--liquidity-data-mode", payload.liquidity_data_mode,
            "--max-option-spread-pct", str(payload.maximum_option_spread_pct),
            "--min-option-open-interest", str(payload.minimum_option_open_interest),
            "--min-option-volume", str(payload.minimum_option_volume),
            "--capital", str(payload.capital),
            "--risk-per-trade-pct", str(payload.risk_per_trade_pct),
            "--max-position-pct", str(payload.max_position_pct),
            "--take-profit-pct", str(payload.take_profit_pct),
            "--stop-loss-pct", str(payload.stop_loss_pct),
            "--minimum-refresh-coverage-pct", str(payload.minimum_refresh_coverage_pct),
            "--maximum-failed-refresh-symbols", str(payload.maximum_failed_refresh_symbols),
            "--refresh-max-retries", str(payload.refresh_max_retries),
            "--refresh-retry-backoff-seconds", str(payload.refresh_retry_backoff_seconds),
            "--refresh-maximum-retry-backoff-seconds", str(payload.refresh_maximum_retry_backoff_seconds),
            "--refresh-retry-jitter-ratio", str(payload.refresh_retry_jitter_ratio),
            "--refresh-rate-limit-cooldown-seconds", str(payload.refresh_rate_limit_cooldown_seconds),
            "--refresh-circuit-breaker-threshold", str(payload.refresh_circuit_breaker_threshold),
            "--refresh-circuit-breaker-cooldown-seconds", str(payload.refresh_circuit_breaker_cooldown_seconds),
            "--report-date", report_date,
        ]
        symbols = [symbol.strip().upper() for symbol in payload.symbols if symbol.strip()]
        if symbols:
            args += ["--symbols", ",".join(dict.fromkeys(symbols))]
        if payload.auto_refresh:
            args.append("--auto-refresh")
        if payload.continue_on_degraded_refresh:
            args.append("--continue-on-degraded-refresh")
        else:
            args.append("--block-on-degraded-refresh")
        return self._start(RunKind.DAILY_SCAN, payload.model_dump(mode="json"), args, requested_by, report_date)

    def _start(self, kind: RunKind, request: dict, args: list[str], requested_by: str, report_date: str | None) -> ScannerRun:
        run = ScannerRun(
            run_id=uuid4().hex,
            kind=kind,
            status=RunStatus.QUEUED,
            requested_by=requested_by,
            request=request,
            command=[sys.executable, *args],
            report_date=report_date,
        )
        self._save(run)
        thread = threading.Thread(target=self._execute, args=(run.run_id,), daemon=True, name=f"m43-{run.run_id[:8]}")
        self._threads[run.run_id] = thread
        thread.start()
        return run

    def _execute(self, run_id: str) -> None:
        run = self.get(run_id)
        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        self._save(run)
        try:
            completed = subprocess.run(
                run.command,
                cwd=self.repository_root,
                text=True,
                capture_output=True,
                check=False,
                timeout=7200,
            )
            run.exit_code = completed.returncode
            run.stdout = completed.stdout[-100000:]
            run.stderr = completed.stderr[-100000:]
            run.status = RunStatus.SUCCEEDED if completed.returncode == 0 else RunStatus.FAILED
            if run.kind == RunKind.DAILY_SCAN and run.report_date:
                self._attach_scan_results(run)
            else:
                run.summary = self._refresh_summary(run.stdout)
        except Exception as exc:
            run.status = RunStatus.FAILED
            run.stderr = f"{type(exc).__name__}: {exc}"
        finally:
            run.completed_at = datetime.now(timezone.utc)
            self._save(run)
            self._threads.pop(run_id, None)

    @staticmethod
    def _refresh_summary(stdout: str) -> dict[str, str]:
        keys = {
            "Requested Symbols": "requested_symbols",
            "Attempted Symbols": "attempted_symbols",
            "Succeeded Symbols": "succeeded_symbols",
            "Failed Symbols": "failed_symbols",
            "Skipped Fresh Symbols": "skipped_fresh_symbols",
            "Rows Upserted": "rows_upserted",
            "Coverage": "coverage",
            "Status": "population_status",
            "Eligible To Continue": "eligible_to_continue",
            "Excluded Symbols": "excluded_symbols",
            "Provider": "provider",
            "Provider Status": "provider_status",
            "Provider Requests": "provider_requests",
            "Provider Retries": "provider_retries",
            "Provider Rate Limits": "provider_rate_limits",
            "Provider Circuit Opens": "provider_circuit_opens",
            "Suppressed Provider Log Lines": "suppressed_provider_log_lines",
            "Provider Affected Symbols": "provider_affected_symbols",
            "Provider Affected Symbol Count": "provider_affected_symbol_count",
            "Scan Skipped Symbols": "scan_skipped_symbols",
            "Scan Provider Rate Limit": "scan_provider_rate_limit",
            "Scan Cache Coverage": "scan_cache_coverage",
            "Scan No Data": "scan_no_data",
            "Scan Transient Provider": "scan_transient_provider",
        }
        summary: dict[str, str] = {}
        for line in stdout.splitlines():
            for label, key in keys.items():
                if line.strip().startswith(label):
                    summary[key] = line.strip()[len(label):].strip()
        return summary

    def _attach_scan_results(self, run: ScannerRun) -> None:
        daily = self.repository_root / "reports" / "daily" / str(run.report_date)
        recommendations = daily / "recommendations.json"
        trades = daily / "live_trade_candidates.json"
        for name, path in {
            "recommendations_json": recommendations,
            "recommendations_csv": daily / "recommendations.csv",
            "recommendations_html": daily / "report.html",
            "trades_json": trades,
            "trades_csv": daily / "live_trade_candidates.csv",
            "trades_html": daily / "live_trade_candidates.html",
        }.items():
            if path.exists():
                run.artifacts[name] = str(path.relative_to(self.repository_root))
        rec_payload = self._read_json(recommendations)
        trade_payload = self._read_json(trades)
        candidates = rec_payload.get("candidates", []) if isinstance(rec_payload, dict) else []
        live_trades = trade_payload.get("trades", []) if isinstance(trade_payload, dict) else []
        refresh_summary = self._refresh_summary(run.stdout)
        run.summary = {
            **refresh_summary,
            "symbols_scanned": rec_payload.get("metadata", {}).get("symbols_scanned", 0) if isinstance(rec_payload, dict) else 0,
            "candidate_count": len(candidates),
            "trade_count": len(live_trades),
            "top_score": max((float(item.get("ai_score", 0)) for item in candidates), default=0),
        }

    @staticmethod
    def _read_json(path: Path) -> dict:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def results(self, run_id: str) -> dict:
        run = self.get(run_id)
        if run.kind != RunKind.DAILY_SCAN or not run.report_date:
            return {"run": run.model_dump(mode="json"), "recommendations": {}, "trades": {}}
        daily = self.repository_root / "reports" / "daily" / run.report_date
        return {
            "run": run.model_dump(mode="json"),
            "recommendations": self._read_json(daily / "recommendations.json"),
            "trades": self._read_json(daily / "live_trade_candidates.json"),
        }
