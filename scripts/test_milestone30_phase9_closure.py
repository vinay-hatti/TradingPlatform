from pathlib import Path

REQUIRED = (
    "observability_policy.py",
    "structured_logging_service.py",
    "metrics_registry.py",
    "distributed_tracing_service.py",
    "instrumentation_policy.py",
    "runtime_metrics_collector.py",
    "trace_propagation.py",
    "metrics_aggregation_service.py",
    "prometheus_exposition_service.py",
    "log_export_pipeline.py",
    "trace_export_pipeline.py",
    "slo_engine.py",
    "error_budget_engine.py",
    "alert_rule_engine.py",
    "telemetry_retention_service.py",
    "observability_reporting.py",
    "observability_dashboard.py",
    "observability_cli.py",
)

def main():
    root = Path(__file__).resolve().parents[1]
    package = root / "src/trading_ai/observability"
    for name in REQUIRED:
        assert (package / name).exists(), name
    status = (root / "updated_PROJECT_STATUS.md").read_text(encoding="utf-8")
    assert "Steps 1–5: COMPLETE" in status
    assert "Milestone 30 Phase 10" in status
    print("All Milestone 30 Phase 9 closure assertions passed.")

if __name__ == "__main__":
    main()
