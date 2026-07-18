from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from trading_ai.ui.api.deployment_recovery import service as service_dependency
from trading_ai.ui.app import create_app
from trading_ai.ui.deployment.repository import DeploymentRecoveryRepository
from trading_ai.ui.services.deployment_recovery_service import (
    DeploymentRecoveryService,
)


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        project = root / "project"
        (project / "src").mkdir(parents=True)
        (project / "scripts").mkdir(parents=True)
        (project / "src" / "sample.py").write_text("print('ok')\n")
        (project / "scripts" / "run.py").write_text("print('run')\n")
        (project / "pyproject.toml").write_text("[project]\nname='test'\n")
        (project / "reports" / "ui").mkdir(parents=True)
        (project / "reports" / "ui" / "state.json").write_text("{}\n")

        service = DeploymentRecoveryService(
            repository=DeploymentRecoveryRepository(
                root / "deployment_state.json"
            ),
            project_root=project,
            artifact_root=root / "artifacts",
            backup_root=root / "backups",
            restore_root=root / "restored",
        )

        package = service.create_package(
            "32.4.0",
            "DEV",
            "phase4-tester",
        )
        assert Path(package.archive_path).exists()
        assert len(package.checksum_sha256) == 64

        promotion = service.promote(
            package.package_id,
            "DEV",
            "TEST",
            "phase4-tester",
            "Promote validated phase four package",
            "CONFIRM-PROMOTION-phase4",
        )
        assert promotion.status == "PROMOTED"

        rejected = service.promote(
            package.package_id,
            "DEV",
            "PRODUCTION",
            "phase4-tester",
            "Invalid direct production promotion",
            "CONFIRM-PROMOTION-phase4",
        )
        assert rejected.status == "REJECTED"

        runtime = service.register_runtime(
            "phase4-dummy",
            ["python", "-c", "import time; time.sleep(30)"],
            str(root / "runtime.log"),
        )
        assert runtime.status == "STOPPED"

        started = service.start_runtime(
            "phase4-dummy",
            "CONFIRM-RUNTIME-phase4",
        )
        assert started.status == "RUNNING"
        assert started.pid is not None

        stopped = service.stop_runtime(
            "phase4-dummy",
            "CONFIRM-RUNTIME-phase4",
        )
        assert stopped.status == "STOPPED"

        backup = service.create_backup(
            "phase4-tester",
            "Create phase four recovery checkpoint",
        )
        assert Path(backup.archive_path).exists()

        verified = service.verify_backup(backup.backup_id)
        assert verified.status == "VERIFIED"

        restored = service.restore_backup(
            backup.backup_id,
            "CONFIRM-RESTORE-phase4",
        )
        assert restored.status == "RESTORED"
        assert (root / "restored" / backup.backup_id).exists()

        state = service.state()
        assert state.summary.package_count == 1
        assert state.summary.backup_count == 1
        assert state.summary.recovery_readiness == "READY"

        app = create_app()
        app.dependency_overrides[service_dependency] = lambda: service
        client = TestClient(app)

        response = client.get("/api/v1/deployment-recovery")
        assert response.status_code == 200
        assert response.json()["summary"]["recovery_readiness"] == "READY"

        create_response = client.post(
            "/api/v1/deployment-recovery/packages",
            json={
                "version": "32.4.1",
                "environment": "TEST",
                "requested_by": "api-tester",
            },
        )
        assert create_response.status_code == 200

    print(
        "All Milestone 32 Phase 4 Deployment Packaging, Environment "
        "Promotion, Runtime Supervision, Backup, and Recovery assertions passed."
    )


if __name__ == "__main__":
    main()
