from trading_ai.ui.services.workstation_release_service import (
    WorkstationReleaseService,
)


def main():
    result = WorkstationReleaseService().get()
    print(f"Release: {result.summary.release_version}")
    print(f"Status: {result.summary.overall_status}")
    print(f"Available modules: {result.summary.available_modules}")
    print(f"Unavailable modules: {result.summary.unavailable_modules}")
    print(f"Passing checks: {result.summary.passing_checks}")
    print(f"Warning checks: {result.summary.warning_checks}")
    print(f"Failing checks: {result.summary.failing_checks}")
    print("Modules:")
    for module in result.modules:
        print(f"- {module.name}: {module.status} ({module.api_path})")
    print("Readiness:")
    for check in result.readiness:
        print(f"- {check.name}: {check.status}")


if __name__ == "__main__":
    main()
