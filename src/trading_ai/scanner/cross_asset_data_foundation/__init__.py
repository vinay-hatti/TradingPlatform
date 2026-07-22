from .contracts import (
    AssetClass,
    CrossAssetFeatureProfile,
    CrossAssetGovernanceStatus,
    CrossAssetRunProfile,
    CrossAssetUniverseMember,
)
from .engine import CrossAssetFeatureEngine
from .policy import CrossAssetFeaturePolicy
from .universe import default_cross_asset_universe

__all__ = [
    "AssetClass",
    "CrossAssetFeatureProfile",
    "CrossAssetGovernanceStatus",
    "CrossAssetRunProfile",
    "CrossAssetUniverseMember",
    "CrossAssetFeatureEngine",
    "CrossAssetFeaturePolicy",
    "default_cross_asset_universe",
]


def __getattr__(name: str):
    # Avoid importing the database-backed service when callers only need
    # contracts, policy, universe definitions, serialization, or the engine.
    if name == "CrossAssetFeatureService":
        from .service import CrossAssetFeatureService

        return CrossAssetFeatureService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
