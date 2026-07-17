from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    polygon_api_key: str = "demo"

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "trading_ai"
    db_user: str = "vinay.hatti"
    db_password: str = "postgres"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:"
            f"{self.db_password}@"
            f"{self.db_host}:"
            f"{self.db_port}/"
            f"{self.db_name}"
        )


settings = Settings()
"""Exports to merge into the existing src/trading_ai/config/__init__.py if desired."""

from .production_configuration import ProductionConfigurationLoader
from .production_runtime_engine import ProductionRuntimeSafetyEngine
from .production_runtime_policy import ProductionRuntimePolicy
from .production_runtime_profile import (
    ProductionConfigurationProfile,
    ProductionRuntimeProfile,
    RuntimeCheckProfile,
    SecretResolutionProfile,
)
from .production_runtime_service import ProductionRuntimeSafetyService
from .secret_provider import (
    CompositeSecretProvider,
    EnvironmentSecretProvider,
    FileSecretProvider,
    MappingSecretProvider,
    SecretProvider,
)

__all__ = [
    "CompositeSecretProvider",
    "EnvironmentSecretProvider",
    "FileSecretProvider",
    "MappingSecretProvider",
    "ProductionConfigurationLoader",
    "ProductionConfigurationProfile",
    "ProductionRuntimePolicy",
    "ProductionRuntimeProfile",
    "ProductionRuntimeSafetyEngine",
    "ProductionRuntimeSafetyService",
    "RuntimeCheckProfile",
    "SecretProvider",
    "SecretResolutionProfile",
]
"""Optional exports to merge into the existing config package __init__.py."""

from .environment_profile import EnvironmentProfile, EnvironmentPromotionProfile, EnvironmentRegistryProfile
from .environment_promotion_engine import EnvironmentPromotionEngine
from .environment_registry import EnvironmentConfigurationRegistry, stable_configuration_hash
from .environment_registry_policy import EnvironmentRegistryPolicy
from .environment_registry_service import EnvironmentRegistryService

__all__ = [
    "EnvironmentConfigurationRegistry",
    "EnvironmentProfile",
    "EnvironmentPromotionEngine",
    "EnvironmentPromotionProfile",
    "EnvironmentRegistryPolicy",
    "EnvironmentRegistryProfile",
    "EnvironmentRegistryService",
    "stable_configuration_hash",
]
"""Optional exports for Milestone 30 Phase 1 Step 3."""

from .credential_health_engine import CredentialHealthEngine, secret_fingerprint
from .secret_governance_policy import SecretGovernancePolicy
from .secret_governance_profile import (
    CredentialHealthCheckProfile,
    CredentialHealthProfile,
    SecretGovernanceProfile,
    SecretInventoryEntryProfile,
    SecretRotationProfile,
)
from .secret_governance_service import SecretGovernanceService
from .secret_inventory_registry import SecretInventoryRegistry

__all__ = [
    "CredentialHealthCheckProfile",
    "CredentialHealthEngine",
    "CredentialHealthProfile",
    "SecretGovernancePolicy",
    "SecretGovernanceProfile",
    "SecretGovernanceService",
    "SecretInventoryEntryProfile",
    "SecretInventoryRegistry",
    "SecretRotationProfile",
    "secret_fingerprint",
]
"""Optional exports for Milestone 30 Phase 1 Step 4."""

from .startup_readiness_engine import StartupReadinessEngine
from .startup_readiness_policy import StartupReadinessPolicy
from .startup_readiness_profile import (
    StartupGateCheckProfile,
    StartupReadinessProfile,
)
from .startup_readiness_service import (
    StartupReadinessService,
    configuration_fingerprint,
)

__all__ = [
    "StartupGateCheckProfile",
    "StartupReadinessEngine",
    "StartupReadinessPolicy",
    "StartupReadinessProfile",
    "StartupReadinessService",
    "configuration_fingerprint",
]
