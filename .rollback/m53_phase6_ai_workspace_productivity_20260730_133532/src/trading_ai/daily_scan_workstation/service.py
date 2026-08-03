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
            "--report-date", report_date,
        ]
        symbols = [symbol.strip().upper() for symbol in payload.symbols if symbol.strip()]
        if symbols:
            args += ["--symbols", ",".join(dict.fromkeys(symbols))]
        request_payload = payload.model_dump(mode="json")
        request_payload["data_access"] = {
            "mode": "DATABASE_ONLY",
            "read_only": True,
            "network_access": False,
            "ingestion_allowed": False,
        }
        return self._start(
            RunKind.DAILY_SCAN,
            request_payload,
            args,
            requested_by,
            report_date,
        )
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

    @staticmethod
    def _number(item: dict, key: str, default: float = 0.0) -> float:
        try:
            return float(item.get(key, default))
        except (TypeError, ValueError):
            return default

    @classmethod
    def _passes_institutional_filters(cls, item: dict, request: dict) -> bool:
        signal = str(item.get("signal", "")).upper()
        direction = str(request.get("direction", "both")).lower()
        if direction == "bullish" and signal not in {"CALL", "BULLISH", "BUY"}:
            return False
        if direction == "bearish" and signal not in {"PUT", "BEARISH", "SELL"}:
            return False
        numeric_rules = (
            ("trend_quality_score", "minimum_trend_quality_score", ">="),
            ("trend_alignment_score", "minimum_trend_alignment_score", ">="),
            ("trend_confidence", "minimum_trend_confidence", ">="),
            ("transition_confirmation_score", "minimum_transition_confirmation_score", ">="),
            ("reversal_risk_score", "maximum_reversal_risk_score", "<="),
            ("exhaustion_risk_score", "maximum_exhaustion_risk_score", "<="),
            ("dealer_score_adjustment", "minimum_dealer_score_adjustment", ">="),
            ("market_structure_confidence", "minimum_market_structure_confidence", ">="),
            ("participation_score", "minimum_participation_score", ">="),
            ("leadership_score", "minimum_leadership_score", ">="),
            ("institutional_conviction_score", "minimum_institutional_conviction_score", ">="),
            ("deterioration_risk_score", "maximum_deterioration_risk_score", "<="),
            ("breadth_confirmation_score", "minimum_breadth_confirmation_score", ">="),
            ("cross_asset_confirmation_score", "minimum_cross_asset_confirmation_score", ">="),
        )
        for value_key, threshold_key, operator in numeric_rules:
            threshold = float(request.get(threshold_key, 0.0 if operator == ">=" else 100.0))
            value = cls._number(item, value_key, 0.0 if operator == ">=" else 100.0)
            if operator == ">=" and value < threshold:
                return False
            if operator == "<=" and value > threshold:
                return False
        stages = {str(v).upper() for v in request.get("allowed_trend_stages", []) if str(v).strip()}
        if stages and str(item.get("trend_stage", "UNAVAILABLE")).upper() not in stages:
            return False
        if request.get("require_breakout") and str(item.get("breakout_state", "UNAVAILABLE")).upper() not in {"BREAKOUT", "BREAKDOWN", "CONFIRMED_BREAKOUT", "CONFIRMED_BREAKDOWN"}:
            return False
        if request.get("require_fresh_dealer_context") and str(item.get("dealer_context_status", "MISSING")).upper() != "FRESH":
            return False
        return True

    @classmethod
    def _filtered_payload(cls, payload: dict, request: dict, collection_key: str) -> dict:
        if not isinstance(payload, dict):
            return {}
        output = dict(payload)
        rows = payload.get(collection_key, [])
        if not isinstance(rows, list):
            return output
        filtered = [row for row in rows if isinstance(row, dict) and cls._passes_institutional_filters(row, request)]
        output[collection_key] = filtered
        metadata = dict(output.get("metadata", {})) if isinstance(output.get("metadata"), dict) else {}
        metadata.update({"institutional_filters_applied": True, "pre_filter_count": len(rows), "post_filter_count": len(filtered)})
        output["metadata"] = metadata
        return output

    def results(self, run_id: str) -> dict:
        run = self.get(run_id)
        if run.kind != RunKind.DAILY_SCAN or not run.report_date:
            return {"run": run.model_dump(mode="json"), "recommendations": {}, "trades": {}}
        daily = self.repository_root / "reports" / "daily" / run.report_date
        recommendations = self._filtered_payload(self._read_json(daily / "recommendations.json"), run.request, "candidates")
        trades = self._filtered_payload(self._read_json(daily / "live_trade_candidates.json"), run.request, "trades")
        run_payload = run.model_dump(mode="json")
        run_payload["summary"] = {**run_payload.get("summary", {}), "filtered_candidate_count": len(recommendations.get("candidates", [])), "filtered_trade_count": len(trades.get("trades", []))}
        return {"run": run_payload, "recommendations": recommendations, "trades": trades}
