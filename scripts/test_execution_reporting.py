from pathlib import Path
from types import SimpleNamespace
import tempfile
from trading_ai.backtest.report import BacktestReport


def main():
    venue=SimpleNamespace(rank=1,venue="CBOE",order_count=4,average_shortfall_bps=12.0,average_fill_ratio=1.0,average_fill_delay_seconds=2.0,execution_score=88.0,execution_grade="A")
    order=SimpleNamespace(order_id="O1",benchmark_shortfall_bps=12.0)
    aggregation=SimpleNamespace(venues=[venue],orders=[order])
    bench=SimpleNamespace(benchmark_name="MIDPOINT",order_count=4,average_shortfall_bps=10.0,median_shortfall_bps=9.0,p90_shortfall_bps=15.0,benchmark_score=90.0,benchmark_grade="A")
    benchmark=SimpleNamespace(summaries=[bench])
    route=SimpleNamespace(rank=1,route_name="CBOE",order_count=4,route_score=91.0,confidence_score=85.0,average_shortfall_bps=10.0,recommended=True)
    routing=SimpleNamespace(venue_recommendations=[route])
    profile=SimpleNamespace(valid=True,order_count=4,execution_score=88.0,execution_grade="A",execution_severity="LOW",average_shortfall_bps=12.0,average_fill_ratio=1.0,average_latency_seconds=2.0,best_benchmark="MIDPOINT",recommended_venue="CBOE",recommended_broker="BROKER_A",routing_score=91.0,aggregation_profile=aggregation,benchmark_profile=benchmark,routing_profile=routing)
    trade={"symbol":"AAPL","net_pnl":100.0,"entry_date":"2026-01-01","exit_date":"2026-01-02","metadata":{"execution_integration_profile":profile}}
    path=Path(tempfile.gettempdir())/"phase9_execution_report.html"
    html=BacktestReport().generate([trade],path=str(path))
    if html is None or str(html) == str(path): html=path.read_text()
    assert "Execution Analytics &amp; Routing Intelligence" in html
    assert "Venue Execution Comparison" in html
    assert "Benchmark Comparison" in html
    assert "Execution Shortfall by Order" in html
    fallback=BacktestReport().generate([],path=str(path))
    if fallback is None or str(fallback) == str(path): fallback=path.read_text()
    assert "No valid Phase 9 execution-analytics profile is attached." in fallback
    print("All Phase 9 execution reporting assertions passed.")

if __name__=="__main__": main()
