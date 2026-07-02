from trading_ai.backtest.metrics import BacktestMetrics
from trading_ai.backtest.equity import EquityCurveBuilder
from trading_ai.backtest.report import BacktestReport


class BacktestEngine:

    def __init__(self, initial_capital=100000.0):
        self.initial_capital = initial_capital
        self.metrics = BacktestMetrics()
        self.equity = EquityCurveBuilder()
        self.report = BacktestReport(initial_capital=initial_capital)

    def run(self, trades, report_path="reports/backtest.html"):

        metrics = self.metrics.calculate(
            trades,
            initial_capital=self.initial_capital,
        )

        equity_curve = self.equity.build(
            trades,
            initial_capital=self.initial_capital,
        )

        self.report.generate(
            trades,
            path=report_path,
        )

        return {
            "trades": trades,
            "metrics": metrics,
            "equity_curve": equity_curve,
            "report_path": report_path,
        }
