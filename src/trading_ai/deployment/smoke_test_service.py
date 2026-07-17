from __future__ import annotations

from dataclasses import dataclass, field
import subprocess
from time import perf_counter

from .release_validation_profile import ValidationCheckResult, ValidationFinding


@dataclass(frozen=True)
class SmokeTestDefinition:
    test_id: str
    command: tuple[str, ...]
    required: bool = True
    timeout_seconds: float | None = None
    environment: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SmokeTestExecution:
    test_id: str
    passed: bool
    return_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_ms: float


class SmokeTestService:
    def execute(
        self,
        tests: tuple[SmokeTestDefinition, ...],
        *,
        default_timeout_seconds: float = 120.0,
        cwd: str | None = None,
        base_environment: dict[str, str] | None = None,
    ) -> tuple[tuple[SmokeTestExecution, ...], ValidationCheckResult]:
        executions: list[SmokeTestExecution] = []
        findings: list[ValidationFinding] = []
        overall_started = perf_counter()
        import os
        for test in tests:
            started = perf_counter()
            env = os.environ.copy()
            env.update(base_environment or {})
            env.update(test.environment)
            try:
                result = subprocess.run(
                    list(test.command), cwd=cwd, env=env,
                    capture_output=True, text=True,
                    timeout=test.timeout_seconds or default_timeout_seconds,
                )
                passed = result.returncode == 0
                execution = SmokeTestExecution(
                    test_id=test.test_id, passed=passed,
                    return_code=result.returncode,
                    stdout=result.stdout, stderr=result.stderr,
                    timed_out=False,
                    duration_ms=(perf_counter() - started) * 1000,
                )
            except subprocess.TimeoutExpired as exc:
                passed = False
                execution = SmokeTestExecution(
                    test_id=test.test_id, passed=False,
                    return_code=None,
                    stdout=(exc.stdout or '') if isinstance(exc.stdout, str) else '',
                    stderr=(exc.stderr or '') if isinstance(exc.stderr, str) else '',
                    timed_out=True,
                    duration_ms=(perf_counter() - started) * 1000,
                )
            executions.append(execution)
            if not passed:
                findings.append(ValidationFinding(
                    check_id=f'smoke.{test.test_id}', category='SMOKE_TEST',
                    severity='CRITICAL' if test.required else 'WARNING',
                    status='FAILED',
                    summary=f'Smoke test {test.test_id} failed.',
                    details={
                        'return_code': execution.return_code,
                        'timed_out': execution.timed_out,
                    },
                    remediation='Correct the release or runtime before promotion.',
                ))
        required_failures = sum(
            not execution.passed and definition.required
            for execution, definition in zip(executions, tests)
        )
        optional_failures = sum(
            not execution.passed and not definition.required
            for execution, definition in zip(executions, tests)
        )
        score = max(0.0, 1.0 - required_failures * 0.5 - optional_failures * 0.1)
        return tuple(executions), ValidationCheckResult(
            check_id='smoke-test-validation', category='SMOKE_TEST',
            passed=not findings, score=score, findings=tuple(findings),
            evidence={'test_count': len(tests), 'executions': [x.__dict__ for x in executions]},
            duration_ms=(perf_counter() - overall_started) * 1000,
        )
