from trading_ai.ui.services.admin_runtime_service import AdminRuntimeService
def main():
    result=AdminRuntimeService().get()
    print(f"Available: {result.available}")
    print(f"Source: {result.source_detail}")
    print(f"Environment: {result.summary.environment}")
    print(f"Profile: {result.summary.profile_name}")
    print(f"Readiness: {result.summary.readiness_status}")
    print(f"Control mode: {result.summary.control_mode}")
    print(f"Components: healthy={result.summary.healthy_components}, degraded={result.summary.degraded_components}, failed={result.summary.failed_components}")
    print(f"Feature flags: enabled={result.summary.enabled_feature_flags}, disabled={result.summary.disabled_feature_flags}")
    print(f"Configuration drift: {result.summary.configuration_drift_count}")
    for notice in result.notices: print(f"- {notice}")
if __name__=="__main__": main()
