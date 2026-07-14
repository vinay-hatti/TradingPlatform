from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from .walk_forward_adapter_profile import (
    WalkForwardAdapterDiagnostics,
    WalkForwardEvaluationResult,
)

BacktestRunner = Callable[[Sequence[Any], dict[str, Any]], Any]


class WalkForwardBacktestAdapter:
    """Normalize existing backtest results into walk-forward evaluator metrics.

    The adapter intentionally accepts a callable instead of importing a concrete
    backtest engine. This preserves the current repository architecture and lets
    callers wrap HistoricalBacktestEngine, experiment runners, or test doubles.
    """

    def __init__(
        self,
        runner: BacktestRunner,
        *,
        initial_capital: float = 100000.0,
        minimum_trades: int = 1,
        annualization_factor: float = 252.0,
    ) -> None:
        if initial_capital <= 0.0:
            raise ValueError("initial_capital must be greater than zero")
        if minimum_trades < 0:
            raise ValueError("minimum_trades cannot be negative")
        self.runner = runner
        self.initial_capital = float(initial_capital)
        self.minimum_trades = int(minimum_trades)
        self.annualization_factor = float(annualization_factor)
        self.diagnostics = WalkForwardAdapterDiagnostics(
            adapter_name=self.__class__.__name__,
        )
        self._parameter_signatures: set[tuple[tuple[str, str], ...]] = set()

    def evaluate(
        self,
        observations: Sequence[Any],
        parameters: dict[str, Any],
    ) -> dict[str, float]:
        result = self.evaluate_detailed(observations, parameters)
        return result.as_engine_metrics()

    def evaluate_detailed(
        self,
        observations: Sequence[Any],
        parameters: dict[str, Any],
    ) -> WalkForwardEvaluationResult:
        self.diagnostics.evaluation_count += 1
        self._parameter_signatures.add(
            tuple(sorted((str(k), repr(v)) for k, v in parameters.items()))
        )
        self.diagnostics.parameter_sets_seen = len(self._parameter_signatures)

        try:
            raw = self.runner(observations, dict(parameters))
            normalized = self._normalize(raw, len(observations))
            if normalized.trade_count < self.minimum_trades:
                normalized.valid = False
                normalized.rejection_reasons.append("MINIMUM_BACKTEST_TRADES_NOT_MET")
                normalized.score = 0.0
            self.diagnostics.successful_evaluations += 1
            return normalized
        except Exception as exc:
            self.diagnostics.failed_evaluations += 1
            self.diagnostics.warnings.append(
                f"BACKTEST_ADAPTER_EVALUATION_FAILED:{type(exc).__name__}"
            )
            return WalkForwardEvaluationResult(
                observation_count=len(observations),
                valid=False,
                rejection_reasons=["BACKTEST_ADAPTER_EVALUATION_FAILED"],
                metadata={
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                },
            )

    def _normalize(
        self,
        raw: Any,
        observation_count: int,
    ) -> WalkForwardEvaluationResult:
        if isinstance(raw, WalkForwardEvaluationResult):
            return raw

        metrics = self._extract_metrics(raw)
        trades = self._extract_trades(raw)
        pnls = [self._pnl(item) for item in trades]

        trade_count = self._int_value(
            metrics,
            ("trades", "trade_count", "total_trades"),
            len(trades),
        )
        net_pnl = self._float_value(
            metrics,
            ("net_pnl", "pnl", "total_pnl"),
            sum(pnls),
        )
        return_pct = self._float_value(
            metrics,
            ("return", "return_pct", "total_return", "net_return"),
            net_pnl / self.initial_capital,
        )
        sharpe = self._float_value(
            metrics,
            ("sharpe", "sharpe_ratio"),
            self._sharpe_from_pnls(pnls),
        )
        drawdown = abs(
            self._float_value(
                metrics,
                ("max_drawdown_pct", "maximum_drawdown_pct", "max_drawdown"),
                self._drawdown_from_pnls(pnls),
            )
        )
        score = self._float_value(
            metrics,
            ("score", "objective_score", "composite_score"),
            self._institutional_score(return_pct, sharpe, drawdown),
        )
        valid = bool(self._value(metrics, ("valid",), True))
        allowed = bool(self._value(metrics, ("allowed",), True))

        return WalkForwardEvaluationResult(
            score=self._finite(score),
            return_pct=self._finite(return_pct),
            sharpe=self._finite(sharpe),
            max_drawdown_pct=max(0.0, self._finite(drawdown)),
            observation_count=observation_count,
            trade_count=trade_count,
            valid=valid and allowed,
            metadata={
                "source_type": type(raw).__name__,
                "net_pnl": net_pnl,
            },
        )

    @staticmethod
    def _extract_metrics(raw: Any) -> Any:
        if isinstance(raw, dict):
            nested = raw.get("metrics")
            return nested if isinstance(nested, dict) else raw
        metrics = getattr(raw, "metrics", None)
        return metrics if metrics is not None else raw

    @staticmethod
    def _extract_trades(raw: Any) -> list[Any]:
        if isinstance(raw, dict):
            trades = raw.get("trades", [])
        else:
            trades = getattr(raw, "trades", [])
        if trades is None:
            return []
        return list(trades)

    @staticmethod
    def _pnl(item: Any) -> float:
        if isinstance(item, dict):
            value = item.get("net_pnl", item.get("pnl", 0.0))
        else:
            value = getattr(item, "net_pnl", getattr(item, "pnl", 0.0))
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _value(source: Any, names: tuple[str, ...], default: Any) -> Any:
        for name in names:
            if isinstance(source, dict) and name in source:
                return source[name]
            if not isinstance(source, dict) and hasattr(source, name):
                return getattr(source, name)
        return default

    def _float_value(
        self,
        source: Any,
        names: tuple[str, ...],
        default: float,
    ) -> float:
        try:
            return float(self._value(source, names, default) or 0.0)
        except (TypeError, ValueError):
            return float(default)

    def _int_value(
        self,
        source: Any,
        names: tuple[str, ...],
        default: int,
    ) -> int:
        try:
            return int(self._value(source, names, default) or 0)
        except (TypeError, ValueError):
            return int(default)

    def _sharpe_from_pnls(self, pnls: list[float]) -> float:
        if len(pnls) < 2:
            return 0.0
        returns = np.asarray(pnls, dtype=float) / self.initial_capital
        std = float(np.std(returns, ddof=1))
        if std <= 0.0:
            return 0.0
        return float(np.mean(returns) / std * math.sqrt(self.annualization_factor))

    def _drawdown_from_pnls(self, pnls: list[float]) -> float:
        if not pnls:
            return 0.0
        equity = self.initial_capital + np.cumsum(np.asarray(pnls, dtype=float))
        peaks = np.maximum.accumulate(np.concatenate(([self.initial_capital], equity)))
        series = np.concatenate(([self.initial_capital], equity))
        drawdowns = np.where(peaks > 0.0, (peaks - series) / peaks, 0.0)
        return float(np.max(drawdowns))

    @staticmethod
    def _institutional_score(
        return_pct: float,
        sharpe: float,
        drawdown_pct: float,
    ) -> float:
        return_component = min(100.0, max(0.0, 50.0 + 200.0 * return_pct))
        sharpe_component = min(100.0, max(0.0, 50.0 + 15.0 * sharpe))
        drawdown_component = max(0.0, 100.0 * (1.0 - drawdown_pct / 0.30))
        return 0.40 * return_component + 0.35 * sharpe_component + 0.25 * drawdown_component

    @staticmethod
    def _finite(value: float) -> float:
        return float(value) if math.isfinite(float(value)) else 0.0
