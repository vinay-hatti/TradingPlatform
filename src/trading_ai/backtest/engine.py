from trading_ai.backtest.metrics import BacktestMetrics
from trading_ai.backtest.equity import EquityCurveBuilder
from trading_ai.backtest.report import BacktestReport
from trading_ai.backtest.exporter import BacktestExporter
from trading_ai.risk.metrics import RiskMetricsEngine
from pathlib import Path


class BacktestEngine:

    def __init__(self, initial_capital=100000.0):
        self.initial_capital = initial_capital
        self.metrics = BacktestMetrics()
        self.equity = EquityCurveBuilder()
        self.report = BacktestReport(initial_capital=initial_capital)
        self.exporter = BacktestExporter()

#    def run(self, trades, report_path="reports/backtest.html"):
    def run(self, trades, report_path="reports/backtest.html", rejected=None):

        metrics = self.metrics.calculate(
            trades,
            initial_capital=self.initial_capital,
        )

        equity_curve = self.equity.build(
            trades,
            initial_capital=self.initial_capital,
        )

        risk_metrics = RiskMetricsEngine().compute(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=self.initial_capital,
        )

        metrics.update(risk_metrics)

        self.report.generate(
            trades,
            path=report_path,
            rejected=rejected or [],
        )

        report_dir = Path(report_path).parent

        self.exporter.export_trades(
            trades,
            report_dir / "trades.csv",
        )

        self.exporter.export_equity(
            equity_curve,
            report_dir / "equity.csv",
        )

        self.exporter.export_metrics(
            metrics,
            report_dir / "metrics.json",
        )

        if rejected is not None:
            self.exporter.export_rejected(
                rejected,
                report_dir / "rejected.csv",
            )

        return {
            "trades": trades,
            "metrics": metrics,
            "equity_curve": equity_curve,
            "report_path": report_path,
        }
