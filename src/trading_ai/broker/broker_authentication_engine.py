from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .broker_policy import BrokerPolicy
from .broker_profile import (
    BrokerAccountProfile,
    BrokerAuthenticationProfile,
    BrokerCapabilitiesProfile,
    BrokerReadinessCheckProfile,
    BrokerReadinessProfile,
)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class BrokerAuthenticationEngine:
    """Evaluate authentication, account, and capability readiness."""

    def __init__(self, policy: BrokerPolicy | None = None) -> None:
        self.policy = policy or BrokerPolicy()
        self.policy.validate()

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95.0:
            return "A", "LOW"
        if score >= 85.0:
            return "B", "MODERATE"
        if score >= 70.0:
            return "C", "SEVERE"
        return "F", "CRITICAL"

    def evaluate_authentication(
        self,
        profile: BrokerAuthenticationProfile,
        *,
        now: datetime | None = None,
    ) -> BrokerAuthenticationProfile:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        current = current.astimezone(timezone.utc)

        authenticated_at = _parse_timestamp(profile.authenticated_at)
        expires_at = _parse_timestamp(profile.expires_at)
        token_age = (
            (current - authenticated_at).total_seconds()
            if authenticated_at is not None
            else None
        )
        seconds_until_expiry = (
            (expires_at - current).total_seconds()
            if expires_at is not None
            else None
        )

        warnings: list[str] = []
        rejections: list[str] = []

        if self.policy.require_authenticated_session and not profile.authenticated:
            rejections.append("BROKER_NOT_AUTHENTICATED")

        if (
            token_age is not None
            and token_age > self.policy.maximum_token_age_seconds
        ):
            rejections.append("BROKER_TOKEN_TOO_OLD")

        if seconds_until_expiry is not None:
            if seconds_until_expiry <= 0:
                rejections.append("BROKER_TOKEN_EXPIRED")
            elif seconds_until_expiry <= self.policy.token_expiry_warning_seconds:
                warnings.append("BROKER_TOKEN_EXPIRY_APPROACHING")

        environment = profile.environment.strip().lower()
        if environment not in self.policy.allowed_environments:
            rejections.append("BROKER_ENVIRONMENT_NOT_ALLOWED")

        if (
            profile.live_trading_enabled
            and self.policy.reject_live_broker_outside_production
            and environment != self.policy.production_environment
        ):
            rejections.append("LIVE_BROKER_OUTSIDE_PRODUCTION")

        score = max(0.0, 100.0 - 25.0 * len(rejections) - 5.0 * len(warnings))
        grade, severity = self._grade(score)
        allowed = not rejections and score >= self.policy.minimum_readiness_score

        return BrokerAuthenticationProfile(
            broker=profile.broker,
            environment=environment,
            authenticated=profile.authenticated,
            session_id=profile.session_id,
            account_id=profile.account_id,
            authenticated_at=profile.authenticated_at,
            expires_at=profile.expires_at,
            token_age_seconds=round(token_age, 3) if token_age is not None else None,
            seconds_until_expiry=(
                round(seconds_until_expiry, 3)
                if seconds_until_expiry is not None
                else None
            ),
            live_trading_enabled=profile.live_trading_enabled,
            score=score,
            grade=grade,
            severity=severity,
            allowed=allowed,
            recommendation=(
                "USE_SESSION"
                if allowed and not warnings
                else "REFRESH_SESSION"
                if allowed
                else "AUTHENTICATE"
            ),
            warnings=tuple(warnings),
            rejection_reasons=tuple(rejections),
            metadata=dict(profile.metadata),
        )

    def evaluate_readiness(
        self,
        authentication: BrokerAuthenticationProfile | None,
        account: BrokerAccountProfile | None,
        capabilities: BrokerCapabilitiesProfile | None,
    ) -> BrokerReadinessProfile:
        checks: list[BrokerReadinessCheckProfile] = []

        def add(
            name: str,
            passed: bool,
            message: str,
            *,
            required: bool = True,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            checks.append(
                BrokerReadinessCheckProfile(
                    name=name,
                    passed=bool(passed),
                    required=required,
                    score=100.0 if passed else 0.0,
                    severity="LOW" if passed else "CRITICAL",
                    message=message,
                    metadata=metadata or {},
                )
            )

        add(
            "authentication",
            authentication is not None and authentication.allowed,
            "Broker authentication must be valid and approved.",
            required=self.policy.require_authenticated_session,
        )
        add(
            "account_profile",
            account is not None,
            "Broker account profile must be available.",
            required=self.policy.require_account_profile,
        )

        if account is not None:
            add(
                "net_liquidation",
                account.net_liquidation > 0
                or not self.policy.require_positive_net_liquidation,
                "Net liquidation must be positive.",
                metadata={"net_liquidation": account.net_liquidation},
            )
            add(
                "buying_power",
                account.buying_power > 0
                or not self.policy.require_positive_buying_power,
                "Buying power must be positive.",
                metadata={"buying_power": account.buying_power},
            )
            add(
                "trading_permission",
                account.trading_permission
                or not self.policy.require_trading_permission,
                "Trading permission must be enabled.",
            )
            add(
                "options_permission",
                account.options_permission
                or not self.policy.require_options_permission,
                "Options permission must be enabled when required.",
                required=self.policy.require_options_permission,
            )
            add(
                "market_data_permission",
                account.market_data_permission
                or not self.policy.require_market_data_permission,
                "Market-data permission must be enabled when required.",
                required=self.policy.require_market_data_permission,
            )

        if capabilities is not None and authentication is not None:
            add(
                "live_capability",
                not authentication.live_trading_enabled
                or capabilities.supports_live_trading,
                "Broker supports requested live trading mode.",
            )

        required_checks = [item for item in checks if item.required]
        failed = [
            item for item in required_checks if not item.passed
        ]
        score = (
            sum(item.score for item in required_checks) / len(required_checks)
            if required_checks else 100.0
        )
        allowed = not failed and score >= self.policy.minimum_readiness_score
        if not self.policy.fail_closed:
            allowed = score >= self.policy.minimum_readiness_score

        grade, severity = self._grade(score)
        broker = (
            authentication.broker
            if authentication is not None
            else account.broker
            if account is not None
            else capabilities.broker
            if capabilities is not None
            else "unknown"
        )
        environment = (
            authentication.environment
            if authentication is not None
            else "unknown"
        )

        return BrokerReadinessProfile(
            valid=True,
            allowed=allowed,
            broker=broker,
            environment=environment,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="READY" if allowed else "BLOCK_BROKER",
            authentication=authentication,
            account=account,
            capabilities=capabilities,
            checks=tuple(checks),
            warnings=(
                authentication.warnings
                if authentication is not None
                else ()
            ),
            rejection_reasons=tuple(
                item.name.upper() for item in failed
            ),
            metadata={
                "required_check_count": len(required_checks),
                "failed_required_check_count": len(failed),
            },
        )
