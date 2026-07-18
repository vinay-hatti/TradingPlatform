from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from trading_ai.ui.deployment.repository import DeploymentRecoveryRepository
from trading_ai.ui.models.deployment_recovery import (
    BackupRecord,
    BackupStatus,
    DeploymentPackage,
    DeploymentRecoveryState,
    DeploymentRecoverySummary,
    PromotionRecord,
    PromotionStatus,
    RuntimeComponent,
    RuntimeStatus,
)


class DeploymentRecoveryService:
    DEFAULT_BACKUP_PATHS = (
        "reports/ui",
        "reports/audit",
        "reports/observability",
        "reports/deployment",
    )

    def __init__(
        self,
        repository: DeploymentRecoveryRepository | None = None,
        project_root: Path | str = ".",
        artifact_root: Path | str = "reports/deployment/artifacts",
        backup_root: Path | str = "reports/backups",
        restore_root: Path | str = "reports/restored",
    ):
        self.repository = repository or DeploymentRecoveryRepository()
        self.project_root = Path(project_root).resolve()
        self.artifact_root = Path(artifact_root)
        self.backup_root = Path(backup_root)
        self.restore_root = Path(restore_root)

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _payload(self):
        payload = self.repository.load()
        payload.setdefault("packages", [])
        payload.setdefault("promotions", [])
        payload.setdefault("runtime_components", [])
        payload.setdefault("backups", [])
        return payload

    def create_package(
        self,
        version: str,
        environment: str,
        requested_by: str,
    ) -> DeploymentPackage:
        payload = self._payload()
        package_id = f"pkg-{uuid4().hex[:16]}"
        package_dir = self.artifact_root / package_id
        package_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "package_id": package_id,
            "version": version,
            "environment": environment,
            "requested_by": requested_by,
            "created_at": self._now().isoformat(),
            "included_roots": ["src", "scripts", "pyproject.toml", "uv.lock"],
            "live_trading_enabled": False,
        }
        manifest_path = package_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        archive_path = package_dir / f"trading-ai-{version}-{environment.lower()}.tar.gz"
        file_count = 0
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(manifest_path, arcname="manifest.json")
            file_count += 1
            for relative in ("src", "scripts", "pyproject.toml", "uv.lock"):
                source = self.project_root / relative
                if source.exists():
                    archive.add(source, arcname=relative)
                    if source.is_file():
                        file_count += 1
                    else:
                        file_count += sum(1 for p in source.rglob("*") if p.is_file())

        package = DeploymentPackage(
            package_id=package_id,
            version=version,
            environment=environment,
            archive_path=str(archive_path),
            manifest_path=str(manifest_path),
            checksum_sha256=self._sha256(archive_path),
            created_at=self._now(),
            file_count=file_count,
            size_bytes=archive_path.stat().st_size,
        )
        payload["packages"].append(package.model_dump(mode="json"))
        self.repository.save(payload)
        return package

    def promote(
        self,
        package_id: str,
        source_environment: str,
        target_environment: str,
        requested_by: str,
        reason: str,
        confirmation_token: str,
    ) -> PromotionRecord:
        payload = self._payload()
        package = next(
            (
                DeploymentPackage.model_validate(item)
                for item in payload["packages"]
                if item["package_id"] == package_id
            ),
            None,
        )
        if package is None:
            raise KeyError(package_id)

        messages: list[str] = []
        status = PromotionStatus.PROMOTED

        allowed = {
            "DEV": {"TEST", "PAPER"},
            "TEST": {"PAPER", "STAGING"},
            "PAPER": {"STAGING"},
            "STAGING": {"PRODUCTION"},
            "PRODUCTION": set(),
        }
        if target_environment not in allowed.get(source_environment, set()):
            status = PromotionStatus.REJECTED
            messages.append("Environment promotion path is not allowed.")

        if target_environment == "PRODUCTION":
            if not confirmation_token.startswith("CONFIRM-PRODUCTION-"):
                status = PromotionStatus.REJECTED
                messages.append(
                    "Production promotion requires CONFIRM-PRODUCTION- token."
                )
            messages.append(
                "Package promotion does not enable live trading."
            )
        elif not confirmation_token.startswith("CONFIRM-PROMOTION-"):
            status = PromotionStatus.REJECTED
            messages.append(
                "Promotion requires CONFIRM-PROMOTION- token."
            )

        archive = Path(package.archive_path)
        if not archive.exists():
            status = PromotionStatus.REJECTED
            messages.append("Package archive is missing.")
        elif self._sha256(archive) != package.checksum_sha256:
            status = PromotionStatus.REJECTED
            messages.append("Package checksum verification failed.")
        else:
            messages.append("Package checksum verified.")

        promotion = PromotionRecord(
            promotion_id=f"promo-{uuid4().hex[:16]}",
            package_id=package_id,
            source_environment=source_environment,
            target_environment=target_environment,
            status=status,
            requested_by=requested_by,
            reason=reason,
            requested_at=self._now(),
            completed_at=self._now(),
            validation_messages=messages,
        )
        payload["promotions"].append(promotion.model_dump(mode="json"))
        self.repository.save(payload)
        return promotion

    def register_runtime(
        self,
        name: str,
        command: list[str],
        log_path: str | None = None,
    ) -> RuntimeComponent:
        payload = self._payload()
        existing = next(
            (
                RuntimeComponent.model_validate(item)
                for item in payload["runtime_components"]
                if item["name"] == name
            ),
            None,
        )
        if existing:
            return existing

        component = RuntimeComponent(
            name=name,
            command=command,
            status=RuntimeStatus.STOPPED,
            log_path=log_path,
        )
        payload["runtime_components"].append(component.model_dump(mode="json"))
        self.repository.save(payload)
        return component

    def _runtime(self, payload: dict, name: str) -> RuntimeComponent:
        component = next(
            (
                RuntimeComponent.model_validate(item)
                for item in payload["runtime_components"]
                if item["name"] == name
            ),
            None,
        )
        if component is None:
            raise KeyError(name)
        return component

    def _replace_runtime(self, payload: dict, component: RuntimeComponent):
        payload["runtime_components"] = [
            component.model_dump(mode="json")
            if item["name"] == component.name
            else item
            for item in payload["runtime_components"]
        ]

    def start_runtime(
        self,
        name: str,
        confirmation_token: str,
    ) -> RuntimeComponent:
        if not confirmation_token.startswith("CONFIRM-RUNTIME-"):
            raise PermissionError("Runtime confirmation token is required.")

        payload = self._payload()
        component = self._runtime(payload, name)
        if component.status == RuntimeStatus.RUNNING and component.pid:
            return component

        log_handle = None
        try:
            if component.log_path:
                log_file = Path(component.log_path)
                log_file.parent.mkdir(parents=True, exist_ok=True)
                log_handle = log_file.open("a", encoding="utf-8")

            process = subprocess.Popen(
                component.command,
                cwd=self.project_root,
                stdout=log_handle or subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            component.pid = process.pid
            component.status = RuntimeStatus.RUNNING
            component.started_at = self._now()
            component.last_error = None
        except Exception as error:
            component.status = RuntimeStatus.FAILED
            component.last_error = str(error)
        finally:
            if log_handle:
                log_handle.close()

        self._replace_runtime(payload, component)
        self.repository.save(payload)
        return component

    def stop_runtime(
        self,
        name: str,
        confirmation_token: str,
    ) -> RuntimeComponent:
        if not confirmation_token.startswith("CONFIRM-RUNTIME-"):
            raise PermissionError("Runtime confirmation token is required.")

        payload = self._payload()
        component = self._runtime(payload, name)
        if component.pid:
            try:
                os.killpg(component.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except Exception as error:
                component.last_error = str(error)
                component.status = RuntimeStatus.FAILED
                self._replace_runtime(payload, component)
                self.repository.save(payload)
                return component

        component.status = RuntimeStatus.STOPPED
        component.stopped_at = self._now()
        component.pid = None
        self._replace_runtime(payload, component)
        self.repository.save(payload)
        return component

    def restart_runtime(
        self,
        name: str,
        confirmation_token: str,
    ) -> RuntimeComponent:
        stopped = self.stop_runtime(name, confirmation_token)
        started = self.start_runtime(name, confirmation_token)
        started.restart_count = stopped.restart_count + 1
        payload = self._payload()
        self._replace_runtime(payload, started)
        self.repository.save(payload)
        return started

    def refresh_runtime_statuses(self):
        payload = self._payload()
        refreshed = []
        for item in payload["runtime_components"]:
            component = RuntimeComponent.model_validate(item)
            if component.pid:
                try:
                    os.kill(component.pid, 0)
                    component.status = RuntimeStatus.RUNNING
                except ProcessLookupError:
                    component.status = RuntimeStatus.STOPPED
                    component.pid = None
                except PermissionError:
                    component.status = RuntimeStatus.UNKNOWN
            refreshed.append(component.model_dump(mode="json"))
        payload["runtime_components"] = refreshed
        self.repository.save(payload)

    def create_backup(self, actor: str, reason: str) -> BackupRecord:
        payload = self._payload()
        backup_id = f"backup-{uuid4().hex[:16]}"
        self.backup_root.mkdir(parents=True, exist_ok=True)
        archive_path = self.backup_root / f"{backup_id}.tar.gz"

        included: list[str] = []
        with tarfile.open(archive_path, "w:gz") as archive:
            metadata = {
                "backup_id": backup_id,
                "actor": actor,
                "reason": reason,
                "created_at": self._now().isoformat(),
            }
            metadata_path = self.backup_root / f"{backup_id}.json"
            metadata_path.write_text(
                json.dumps(metadata, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            archive.add(metadata_path, arcname="backup_manifest.json")
            for relative in self.DEFAULT_BACKUP_PATHS:
                source = self.project_root / relative
                if source.exists():
                    archive.add(source, arcname=relative)
                    included.append(relative)
            metadata_path.unlink(missing_ok=True)

        backup = BackupRecord(
            backup_id=backup_id,
            archive_path=str(archive_path),
            checksum_sha256=self._sha256(archive_path),
            status=BackupStatus.CREATED,
            created_at=self._now(),
            included_paths=included,
            size_bytes=archive_path.stat().st_size,
        )
        payload["backups"].append(backup.model_dump(mode="json"))
        self.repository.save(payload)
        return backup

    def verify_backup(self, backup_id: str) -> BackupRecord:
        payload = self._payload()
        backup = next(
            (
                BackupRecord.model_validate(item)
                for item in payload["backups"]
                if item["backup_id"] == backup_id
            ),
            None,
        )
        if backup is None:
            raise KeyError(backup_id)

        archive = Path(backup.archive_path)
        valid = (
            archive.exists()
            and self._sha256(archive) == backup.checksum_sha256
        )
        if valid:
            with tarfile.open(archive, "r:gz") as handle:
                handle.getmembers()
            backup.status = BackupStatus.VERIFIED
            backup.verified_at = self._now()
        else:
            backup.status = BackupStatus.FAILED

        payload["backups"] = [
            backup.model_dump(mode="json")
            if item["backup_id"] == backup_id
            else item
            for item in payload["backups"]
        ]
        self.repository.save(payload)
        return backup

    def restore_backup(
        self,
        backup_id: str,
        confirmation_token: str,
    ) -> BackupRecord:
        if not confirmation_token.startswith("CONFIRM-RESTORE-"):
            raise PermissionError("Restore confirmation token is required.")

        backup = self.verify_backup(backup_id)
        if backup.status != BackupStatus.VERIFIED:
            raise ValueError("Backup verification failed.")

        destination = self.restore_root / backup_id
        destination.mkdir(parents=True, exist_ok=True)
        with tarfile.open(backup.archive_path, "r:gz") as archive:
            archive.extractall(destination)

        payload = self._payload()
        backup.status = BackupStatus.RESTORED
        backup.restored_at = self._now()
        payload["backups"] = [
            backup.model_dump(mode="json")
            if item["backup_id"] == backup_id
            else item
            for item in payload["backups"]
        ]
        self.repository.save(payload)
        return backup

    def state(self) -> DeploymentRecoveryState:
        self.refresh_runtime_statuses()
        payload = self._payload()
        packages = [
            DeploymentPackage.model_validate(item)
            for item in payload["packages"]
        ]
        promotions = [
            PromotionRecord.model_validate(item)
            for item in payload["promotions"]
        ]
        runtimes = [
            RuntimeComponent.model_validate(item)
            for item in payload["runtime_components"]
        ]
        backups = [
            BackupRecord.model_validate(item)
            for item in payload["backups"]
        ]
        verified_count = sum(
            backup.status in {BackupStatus.VERIFIED, BackupStatus.RESTORED}
            for backup in backups
        )

        return DeploymentRecoveryState(
            generated_at=self._now(),
            summary=DeploymentRecoverySummary(
                package_count=len(packages),
                promotion_count=len(promotions),
                active_runtime_count=sum(
                    runtime.status == RuntimeStatus.RUNNING
                    for runtime in runtimes
                ),
                backup_count=len(backups),
                verified_backup_count=verified_count,
                latest_package_version=packages[-1].version if packages else None,
                recovery_readiness=(
                    "READY" if verified_count > 0 else "NOT_READY"
                ),
            ),
            packages=sorted(
                packages,
                key=lambda item: item.created_at,
                reverse=True,
            ),
            promotions=sorted(
                promotions,
                key=lambda item: item.requested_at,
                reverse=True,
            ),
            runtime_components=runtimes,
            backups=sorted(
                backups,
                key=lambda item: item.created_at,
                reverse=True,
            ),
            notices=[
                "Deployment packages do not enable live trading.",
                "Production promotion requires a dedicated confirmation token.",
                "Restore operations extract to an isolated recovery directory.",
            ],
        )
