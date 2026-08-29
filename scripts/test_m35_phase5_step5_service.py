import json
import tempfile
from datetime import date
from pathlib import Path

from trading_ai.scanner.cross_asset_intelligence.service import (
    CrossAssetIntelligenceService,
)


def dump(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        intermarket_path = root / "intermarket.json"
        sector_path = root / "sector.json"
        correlation_path = root / "correlation.json"
        output_path = root / "intelligence.json"

        dump(
            intermarket_path,
            {
                "market_state": "RISK_ON",
                "confidence": 0.80,
                "governance_status": "READY",
            },
        )
        dump(
            sector_path,
            {
                "rotation_state": "BROAD_RISK_ON",
                "leadership_state": "OFFENSIVE",
                "confidence": 0.75,
                "leaders": ["XLK", "XLY", "XLI"],
                "laggards": ["XLU", "XLP", "XLV"],
                "governance_status": "READY",
            },
        )
        dump(
            correlation_path,
            {
                "correlation_regime": "LOW_CORRELATION",
                "dispersion_regime": "HIGH_DISPERSION",
                "market_structure_state": "SECURITY_SELECTION",
                "correlation_breakdown_ratio": 0.05,
                "confidence": 0.70,
                "governance_status": "READY",
            },
        )

        run_profile = CrossAssetIntelligenceService().run(
            as_of_date=date(2026, 7, 20),
            intermarket_input_path=intermarket_path,
            sector_input_path=sector_path,
            correlation_input_path=correlation_path,
            output_path=output_path,
        )

        assert output_path.exists()
        assert run_profile.macro_regime == "RISK_ON"
        assert run_profile.tactical_bias == "BULLISH"
        assert run_profile.governance_status == "READY"

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["feature_version"] == "m35.phase5.step5.v1"
        assert payload["decision_adjustment"]["allow_new_risk"] is True

    print("Milestone 35 Phase 5 Step 5 service assertions passed.")


if __name__ == "__main__":
    main()
