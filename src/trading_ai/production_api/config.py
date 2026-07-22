from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class ProductionApiSettings:
    environment: str = "development"
    api_key: str | None = None
    require_api_key: bool = False
    allow_mutations: bool = False
    artifact_root: Path = Path("reports")
    portfolio_registry_file: Path = Path("data/portfolio/m36_portfolio_registry.json")
    max_artifact_age_seconds: int = 3600

    @classmethod
    def from_env(cls) -> "ProductionApiSettings":
        root = Path(os.getenv("TRADING_AI_ARTIFACT_ROOT", "reports"))
        return cls(
            environment=os.getenv("TRADING_AI_ENV", "development"),
            api_key=os.getenv("TRADING_AI_API_KEY") or None,
            require_api_key=os.getenv("TRADING_AI_REQUIRE_API_KEY", "false").lower() in {"1", "true", "yes"},
            allow_mutations=os.getenv("TRADING_AI_ALLOW_API_MUTATIONS", "false").lower() in {"1", "true", "yes"},
            artifact_root=root,
            portfolio_registry_file=Path(os.getenv("TRADING_AI_PORTFOLIO_REGISTRY", "data/portfolio/m36_portfolio_registry.json")),
            max_artifact_age_seconds=int(os.getenv("TRADING_AI_MAX_ARTIFACT_AGE_SECONDS", "3600")),
        )
