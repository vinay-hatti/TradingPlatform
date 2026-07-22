from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from .contracts import CrossAssetIntelligenceRunProfile
from .engine import CrossAssetIntelligenceEngine
from .policy import CrossAssetIntelligencePolicy
from .serialization import load_json, write_json_atomic


class CrossAssetIntelligenceService:
    def __init__(
        self,
        policy: CrossAssetIntelligencePolicy | None = None,
    ) -> None:
        self.policy = policy or CrossAssetIntelligencePolicy()
        self.engine = CrossAssetIntelligenceEngine(self.policy)

    def run(
        self,
        *,
        as_of_date: date,
        intermarket_input_path: str | Path,
        sector_input_path: str | Path,
        correlation_input_path: str | Path,
        output_path: str | Path,
    ) -> CrossAssetIntelligenceRunProfile:
        intermarket_profile = load_json(intermarket_input_path)
        sector_profile = load_json(sector_input_path)
        correlation_profile = load_json(correlation_input_path)

        profile = self.engine.evaluate(
            as_of_date=as_of_date,
            intermarket_profile=intermarket_profile,
            sector_profile=sector_profile,
            correlation_profile=correlation_profile,
        )

        write_json_atomic(output_path, profile)

        return CrossAssetIntelligenceRunProfile(
            as_of_date=as_of_date,
            generated_at=datetime.now(timezone.utc),
            intermarket_input_path=str(intermarket_input_path),
            sector_input_path=str(sector_input_path),
            correlation_input_path=str(correlation_input_path),
            output_path=str(output_path),
            macro_regime=profile.macro_regime,
            tactical_bias=profile.tactical_bias,
            opportunity_regime=profile.opportunity_regime,
            systemic_risk_level=profile.systemic_risk_level,
            composite_confidence=profile.composite_confidence,
            governance_status=profile.governance_status.value,
            metadata={
                "feature_version": profile.feature_version,
                "source_governance": profile.source_governance,
                "decision_adjustment": (
                    profile.decision_adjustment.to_dict()
                ),
                "policy": self.policy.__dict__.copy(),
            },
        )
