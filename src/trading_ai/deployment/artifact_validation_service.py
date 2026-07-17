from __future__ import annotations

import hashlib
from pathlib import Path
from time import perf_counter

from .release_contract import ReleaseContract
from .release_validation_profile import (
    ValidationCheckResult,
    ValidationFinding,
)


class ArtifactValidationService:
    def validate(
        self,
        release: ReleaseContract,
        *,
        artifact_path: str | Path | None = None,
        signature_verified: bool | None = None,
        require_exists: bool = True,
        require_checksum: bool = True,
        require_signature: bool = True,
    ) -> ValidationCheckResult:
        started = perf_counter()
        findings: list[ValidationFinding] = []
        path = Path(artifact_path or release.artifact_location)
        exists = path.exists()
        actual_checksum = None
        if require_exists and not exists:
            findings.append(ValidationFinding(
                check_id='artifact.exists', category='ARTIFACT',
                severity='CRITICAL', status='FAILED',
                summary='Release artifact does not exist.',
                details={'path': str(path)},
                remediation='Publish the immutable release artifact.',
            ))
        if exists:
            digest = hashlib.sha256()
            with path.open('rb') as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                    digest.update(chunk)
            actual_checksum = digest.hexdigest()
            if require_checksum and actual_checksum != release.artifact_checksum:
                findings.append(ValidationFinding(
                    check_id='artifact.checksum', category='ARTIFACT',
                    severity='CRITICAL', status='FAILED',
                    summary='Artifact checksum does not match the release contract.',
                    details={
                        'expected': release.artifact_checksum,
                        'actual': actual_checksum,
                    },
                    remediation='Rebuild or republish the correctly signed artifact.',
                ))
        verified = release.artifact_signed if signature_verified is None else signature_verified
        if require_signature and not verified:
            findings.append(ValidationFinding(
                check_id='artifact.signature', category='ARTIFACT',
                severity='CRITICAL', status='FAILED',
                summary='Artifact signature verification failed or was not supplied.',
                remediation='Verify the artifact signature using the trusted release key.',
            ))
        score = max(0.0, 1.0 - 0.5 * len(findings))
        return ValidationCheckResult(
            check_id='artifact-validation', category='ARTIFACT',
            passed=not findings, score=score, findings=tuple(findings),
            evidence={
                'path': str(path), 'exists': exists,
                'actual_checksum': actual_checksum,
                'signature_verified': bool(verified),
            },
            duration_ms=(perf_counter() - started) * 1000,
        )
