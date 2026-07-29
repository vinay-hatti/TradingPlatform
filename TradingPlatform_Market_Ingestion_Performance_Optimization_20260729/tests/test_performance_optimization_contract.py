from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "payload"


def main() -> None:
    ingestion = (PAYLOAD / "scripts/run_market_ingestion.py").read_text(encoding="utf-8")
    pipeline = (PAYLOAD / "src/trading_ai/trend_intelligence/pipeline_service.py").read_text(encoding="utf-8")
    platform = (PAYLOAD / "src/trading_ai/trend_intelligence/platform_integration.py").read_text(encoding="utf-8")

    assert '--trend-execution-mode' in ingestion
    assert 'choices=["in-process", "subprocess"]' in ingestion
    assert 'TrendIntelligencePipelineService' in ingestion
    assert 'metrics": getattr(args, "_trend_pipeline_metrics", None)' in ingestion
    assert 'SELECT symbol, date, close, volume' in pipeline
    assert 'price_data=all_price_data' in pipeline
    assert 'price_data=dated_price_data' in pipeline
    assert 'SELECT DISTINCT ON (symbol)' in platform
    assert 'def contexts(' in platform
    assert 'contexts: list[TrendPlatformContext] | None = None' in platform
    print("Market ingestion performance optimization contract assertions passed.")


if __name__ == "__main__":
    main()
