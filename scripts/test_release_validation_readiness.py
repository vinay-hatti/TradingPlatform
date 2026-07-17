from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile

from trading_ai.deployment.compatibility_validation_service import RuntimeCompatibilityProfile
from trading_ai.deployment.dependency_verification_service import DependencyRequirement
from trading_ai.deployment.migration_configuration_validation_service import (
    ConfigurationValidationInput,
    MigrationValidationInput,
)
from trading_ai.deployment.release_contract import ReleaseContract
from trading_ai.deployment.release_readiness_report import ReleaseReadinessReportBuilder
from trading_ai.deployment.release_validation_service import ReleaseValidationService
from trading_ai.deployment.smoke_test_service import SmokeTestDefinition


def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        artifact = root / 'release.bin'
        artifact.write_bytes(b'institutional-trading-platform-release')
        checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
        release = ReleaseContract(
            release_id='release-1.1.0', version='1.1.0', git_commit='abc123',
            build_timestamp='2026-07-17T12:00:00+00:00',
            artifact_checksum=checksum, artifact_location=str(artifact),
            migration_version='m2', configuration_version='c2',
            supported_database_versions=('17',),
            supported_schema_versions=('m2',),
            minimum_platform_version='1.0.0', maximum_platform_version='2.0.0',
            rollback_supported=True, deployment_targets=('STAGING','PRODUCTION'),
            release_tag='v1.1.0', artifact_signed=True,
        )
        service = ReleaseValidationService()
        result = service.validate(
            release=release, environment='PRODUCTION', artifact_path=artifact,
            signature_verified=True,
            dependencies=(
                DependencyRequirement('sqlalchemy','2.0','2.0',locked=True),
                DependencyRequirement('pydantic','2.0','2.0',locked=True),
            ),
            runtime=RuntimeCompatibilityProfile(
                platform_version='1.1.0', database_version='17', schema_version='m2'
            ),
            migration=MigrationValidationInput(
                current_version='m1', target_version='m2',
                forward_validated=True, rollback_validated=True,
            ),
            configuration=ConfigurationValidationInput(
                version='c2', schema_valid=True,
                secret_references_valid=True, environment_overrides_valid=True,
            ),
            smoke_tests=(
                SmokeTestDefinition(
                    test_id='runtime', command=(sys.executable, '-c', "print('ok')")
                ),
            ),
        )
        assert result.ready, result
        assert result.score == 1.0
        assert result.recommendation == 'RELEASE_READY'
        html = ReleaseReadinessReportBuilder().write_html(root/'readiness.html', result)
        js = ReleaseReadinessReportBuilder().write_json(root/'readiness.json', result)
        assert html.exists() and js.exists()
        assert 'Release Validation and Deployment Readiness' in html.read_text(encoding='utf-8')

        blocked_release = ReleaseContract(**{
            **release.__dict__, 'artifact_checksum': '0' * 64
        })
        blocked = service.validate(
            release=blocked_release, environment='PRODUCTION', artifact_path=artifact,
            signature_verified=False, dependencies=(),
            runtime=RuntimeCompatibilityProfile(
                platform_version='1.1.0', database_version='16', schema_version='m1'
            ),
            migration=MigrationValidationInput(
                current_version='m1', target_version='wrong',
                forward_validated=False, rollback_validated=False,
            ),
            configuration=ConfigurationValidationInput(
                version='wrong', schema_valid=False, secret_references_valid=False,
            ),
            smoke_tests=(
                SmokeTestDefinition(
                    test_id='failure', command=(sys.executable, '-c', 'raise SystemExit(2)')
                ),
            ),
        )
        assert not blocked.ready
        assert blocked.critical_findings >= 1
        assert blocked.recommendation == 'BLOCK_CRITICAL_FINDINGS'

    print('All release validation, dependency verification, smoke-test, readiness-scoring, and reporting assertions passed.')


if __name__ == '__main__':
    main()
