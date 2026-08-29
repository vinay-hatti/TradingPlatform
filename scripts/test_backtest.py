from trading_ai.app.bootstrap import container
from trading_ai.backtest.engine import BacktestEngine
from trading_ai.backtest.execution import ExecutionEngine
from trading_ai.backtest.portfolio import Portfolio

portfolio = Portfolio(100000)

execution = ExecutionEngine()

engine = BacktestEngine(
    scanner=container.scanner,
    portfolio=portfolio,
    execution=execution,
)

results = engine.run(
    symbols=[
        "AAPL",
        "MSFT",
        "NVDA",
        "META",
    ],
    start="2025-01-01",
    end="2025-12-31",
)

for trade in results:
    print(trade)
