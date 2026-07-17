from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from .production_runtime_policy import ProductionRuntimePolicy
from .production_runtime_profile import (
    ProductionConfigurationProfile,
    ProductionRuntimeProfile,
    RuntimeCheckProfile,
    SecretResolutionProfile,
)
from .secret_provider import CompositeSecretProvider, SecretProvider, redact_secret


class ProductionRuntimeSafetyEngine:
    def __init__(self, policy: ProductionRuntimePolicy | None = None) -> None:
        self.policy = policy or ProductionRuntimePolicy()
        self.policy.validate()

    def _check(
        self,
        name: str,
        category: str,
        passed: bool,
        message: str,
        required: bool = True,
        severity: str = "CRITICAL",
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeCheckProfile:
        return RuntimeCheckProfile(
            name=name,
            category=category,
            passed=bool(passed),
            required=required,
            score=100.0 if passed else 0.0,
            severity="LOW" if passed else severity,
            message=message,
            metadata=metadata or {},
        )

    def _resolve_secrets(
        self,
        names: tuple[str, ...],
        provider: SecretProvider | None,
    ) -> tuple[SecretResolutionProfile, ...]:
        rows = []
        for name in names:
            value = None
            provider_name = "unavailable"
            try:
                if isinstance(provider, CompositeSecretProvider):
                    value, provider_name = provider.resolve(name)
                elif provider is not None:
                    value = provider.get(name)
                    provider_name = provider.name if value is not None else "unavailable"
                rows.append(
                    SecretResolutionProfile(
                        name=name,
                        resolved=value is not None,
                        provider=provider_name,
                        redacted_value=redact_secret(value),
                    )
                )
            except Exception as exc:
                rows.append(
                    SecretResolutionProfile(
                        name=name,
                        resolved=False,
                        provider=provider_name,
                        error=str(exc),
                    )
                )
        return tuple(rows)

    def _is_plaintext_sensitive(
        self,
        data: Mapping[str, Any],
        prefix: str = "",
    ) -> list[str]:
        found: list[str] = []
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, Mapping):
                found.extend(self._is_plaintext_sensitive(value, path))
                continue
            normalized = str(key).lower()
            if any(fragment in normalized for fragment in self.policy.sensitive_key_fragments):
                if value not in (None, "", "<redacted>", "****") and not str(value).startswith("${"):
                    found.append(path)
        return found

    def evaluate(
        self,
        configuration: ProductionConfigurationProfile,
        secret_provider: SecretProvider | None = None,
        raw_configuration: Mapping[str, Any] | None = None,
    ) -> ProductionRuntimeProfile:
        env = configuration.environment
        production = env == self.policy.production_environment
        checks: list[RuntimeCheckProfile] = []

        checks.append(self._check(
            "environment",
            "configuration",
            env in self.policy.allowed_environments,
            f"Environment '{env}' is allowed.",
        ))
        checks.append(self._check(
            "debug_mode",
            "configuration",
            not (production and self.policy.reject_debug_in_production and configuration.debug),
            "Debug mode is safe for the selected environment.",
        ))
        checks.append(self._check(
            "live_trading_environment",
            "trading",
            not (
                configuration.live_trading_enabled
                and self.policy.allow_live_trading_only_in_production
                and not production
            ),
            "Live trading is restricted to production.",
        ))
        checks.append(self._check(
            "kill_switch",
            "trading",
            not (
                production
                and self.policy.require_kill_switch_in_production
                and not configuration.kill_switch_enabled
            ),
            "Kill switch is enabled when required.",
        ))
        checks.append(self._check(
            "database",
            "provider",
            not (
                production
                and self.policy.require_database_in_production
                and not configuration.database_url
            ),
            "Database configuration is present when required.",
        ))
        checks.append(self._check(
            "broker_provider",
            "provider",
            not (
                production
                and self.policy.require_broker_in_production
                and not configuration.broker_provider
            ),
            "Broker provider is present when required.",
        ))
        checks.append(self._check(
            "market_data_provider",
            "provider",
            not (
                production
                and self.policy.require_market_data_in_production
                and not configuration.market_data_provider
            ),
            "Market-data provider is present when required.",
        ))

        root = Path(configuration.metadata.get("project_root", Path.cwd()))
        for field_name in self.policy.required_directories:
            raw_path = getattr(configuration, field_name)
            path = Path(raw_path)
            if not path.is_absolute():
                path = root / path
            try:
                path.mkdir(parents=True, exist_ok=True)
                writable = path.is_dir() and os.access(path, os.W_OK)
            except OSError:
                writable = False
            checks.append(self._check(
                field_name,
                "filesystem",
                writable or not self.policy.require_writable_directories,
                f"Runtime directory is writable: {path}",
                metadata={"path": str(path)},
            ))

        for flag, expected in self.policy.required_feature_flags.items():
            actual = configuration.feature_flags.get(flag)
            checks.append(self._check(
                f"feature_flag:{flag}",
                "feature_flag",
                actual is expected,
                f"Feature flag {flag} must be {expected}.",
            ))

        plaintext = self._is_plaintext_sensitive(raw_configuration or {})
        checks.append(self._check(
            "plaintext_secrets",
            "secrets",
            not (
                production
                and self.policy.reject_plaintext_secrets_in_production
                and bool(plaintext)
            ),
            "No plaintext secrets are embedded in production configuration.",
            metadata={"sensitive_paths": plaintext},
        ))

        secrets = self._resolve_secrets(configuration.required_secrets, secret_provider)
        unresolved = [item.name for item in secrets if item.required and not item.resolved]
        checks.append(self._check(
            "required_secrets",
            "secrets",
            not unresolved,
            "All required secrets are resolvable.",
            metadata={"unresolved": unresolved},
        ))

        required = [check for check in checks if check.required]
        failed = [check for check in required if not check.passed]
        score = (
            sum(check.score for check in required) / len(required)
            if required else 100.0
        )
        allowed = not failed and score >= self.policy.minimum_startup_score
        if not self.policy.fail_closed and score >= self.policy.minimum_startup_score:
            allowed = True

        if score >= 95:
            grade, severity = "A", "LOW"
        elif score >= 85:
            grade, severity = "B", "MODERATE"
        elif score >= 70:
            grade, severity = "C", "SEVERE"
        else:
            grade, severity = "F", "CRITICAL"

        warnings = tuple(
            check.message for check in checks if not check.passed and not check.required
        )
        rejection_reasons = tuple(check.name.upper() for check in failed)

        config_snapshot = asdict(configuration)
        if config_snapshot.get("database_url"):
            config_snapshot["database_url"] = "<redacted>"

        return ProductionRuntimeProfile(
            valid=True,
            allowed=allowed,
            environment=env,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="START" if allowed else "BLOCK_STARTUP",
            checks=tuple(checks),
            resolved_secrets=secrets,
            warnings=warnings,
            rejection_reasons=rejection_reasons,
            configuration=config_snapshot,
            metadata={
                "failed_required_check_count": len(failed),
                "required_check_count": len(required),
            },
        )
