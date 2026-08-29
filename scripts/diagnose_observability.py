from trading_ai.ui.services.observability_service import ObservabilityService


def main():
    state = ObservabilityService().state()
    print("=== Workstation Observability ===")
    print(f"Service Status   : {state.summary.service_status}")
    print(f"Readiness        : {state.summary.readiness_status}")
    print(f"Liveness         : {state.summary.liveness_status}")
    print(f"Metrics          : {state.summary.metric_count}")
    print(f"Active Alerts    : {state.summary.active_alert_count}")
    print(f"Critical Alerts  : {state.summary.critical_alert_count}")
    print(f"Warning Alerts   : {state.summary.warning_alert_count}")
    print(f"Structured Log   : {state.summary.structured_log_path}")
    print("\nHealth Checks:")
    for check in state.health_checks:
        print(
            f"- {check.name}: {check.status} "
            f"({check.latency_ms} ms) — {check.detail}"
        )


if __name__ == "__main__":
    main()
