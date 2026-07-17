from trading_ai.observability.observability_reporting import ObservabilityReportBuilder
if __name__ == "__main__":
    print(f"Observability report written: {ObservabilityReportBuilder().write('reports/observability_report.html')}")
