from trading_ai.backtest.metrics import BacktestMetrics
from trading_ai.backtest.equity import EquityCurveBuilder
from trading_ai.backtest.report import BacktestReport
from trading_ai.backtest.exporter import BacktestExporter
from trading_ai.risk.metrics import RiskMetricsEngine
from trading_ai.risk.drawdown_report import DrawdownReporter
from pathlib import Path


class BacktestEngine:

    def __init__(
        self,
        initial_capital=100000.0,
        use_historical_options=False,
        fallback_to_black_scholes=True,
        min_option_volume=0,
        min_open_interest=0,
        max_spread_pct=1.0,
    ):
        self.initial_capital = initial_capital
        self.metrics = BacktestMetrics()
        self.equity = EquityCurveBuilder()
        self.report = BacktestReport(initial_capital=initial_capital)
        self.exporter = BacktestExporter()
        self.use_historical_options = bool(use_historical_options)
        self.fallback_to_black_scholes = bool(fallback_to_black_scholes)
        self.min_option_volume = int(min_option_volume)
        self.min_open_interest = int(min_open_interest)
        self.max_spread_pct = float(max_spread_pct)

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
            equity_curve=equity_curve,
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

        drawdown_path = report_path.replace(
            "report.html",
            "drawdown.csv",
        )

        DrawdownReporter().export_csv(
            equity_curve,
            drawdown_path,
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
            "pricing_config": {
                "use_historical_options": self.use_historical_options,
                "fallback_to_black_scholes": self.fallback_to_black_scholes,
                "min_option_volume": self.min_option_volume,
                "min_open_interest": self.min_open_interest,
                "max_spread_pct": self.max_spread_pct,
            },
        }
