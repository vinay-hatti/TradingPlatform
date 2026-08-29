from trading_ai.observability.observability_dashboard import ObservabilityDashboardBuilder
if __name__ == "__main__":
    print(f"Observability dashboard written: {ObservabilityDashboardBuilder().write('reports/observability_dashboard.json')}")
