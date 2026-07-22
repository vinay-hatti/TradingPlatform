from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .breach_service import PortfolioRiskBreachService
from .exposure_service import PortfolioRiskExposureService
from .policy import PortfolioRiskPolicy
from .profile import PortfolioRiskAssessment, utc_now_iso
from .serialization import read_json, write_json_atomic
from .stress_service import PortfolioStressService


class PortfolioRiskManagementService:
    def __init__(self, policy: PortfolioRiskPolicy | None = None) -> None:
        self.policy = policy or PortfolioRiskPolicy()
        self.policy.validate()
        self.exposure_service = PortfolioRiskExposureService()
        self.stress_service = PortfolioStressService()
        self.breach_service = PortfolioRiskBreachService()

    def assess(self, registry_file: Path, output_file: Path | None = None) -> PortfolioRiskAssessment:
        registry = read_json(registry_file)
        if not registry:
            raise FileNotFoundError(registry_file)
        exposure = self.exposure_service.evaluate(registry)
        stress = self.stress_service.evaluate(exposure["positions"], exposure["nav"], self.policy.maximum_stress_loss_pct)
        metrics, breaches, status, control, recommendations = self.breach_service.evaluate(exposure, stress, self.policy)
        account = registry.get("account", {})
        fingerprint = hashlib.sha256(json.dumps(registry, sort_keys=True, default=str).encode()).hexdigest()
        assessment = PortfolioRiskAssessment(
            assessment_id=f"RISK-{fingerprint[:16].upper()}",
            portfolio_id=str(account.get("portfolio_id", "PRIMARY")),
            generated_at=utc_now_iso(),
            status=status,
            trading_control=control,
            net_liquidation_value=exposure["nav"],
            cash_balance=exposure["cash_balance"],
            capital_committed=exposure["capital_committed"],
            open_position_count=len(exposure["positions"]),
            metrics=metrics,
            breaches=breaches,
            stress_results=stress,
            aggregates=exposure["aggregates"],
            concentration=exposure["concentration"],
            liquidity=exposure["liquidity"],
            recommendations=recommendations,
            warnings=tuple(registry.get("warnings", [])),
            source_registry=str(registry_file),
        )
        if output_file:
            write_json_atomic(output_file, {"policy": self.policy.to_dict(), "assessment": assessment.to_dict()})
        return assessment
