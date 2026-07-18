from trading_ai.ui.services.deployment_recovery_service import (
    DeploymentRecoveryService,
)


def main():
    service = DeploymentRecoveryService()
    service.register_runtime(
        "institutional-workstation",
        [
            "uv",
            "run",
            "uvicorn",
            "trading_ai.ui.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8080",
        ],
        "reports/runtime/institutional-workstation.log",
    )
    state = service.state()

    print("=== Deployment & Recovery ===")
    print(f"Packages          : {state.summary.package_count}")
    print(f"Promotions        : {state.summary.promotion_count}")
    print(f"Active Runtimes   : {state.summary.active_runtime_count}")
    print(f"Backups           : {state.summary.backup_count}")
    print(f"Verified Backups  : {state.summary.verified_backup_count}")
    print(f"Latest Version    : {state.summary.latest_package_version}")
    print(f"Recovery Readiness: {state.summary.recovery_readiness}")


if __name__ == "__main__":
    main()
