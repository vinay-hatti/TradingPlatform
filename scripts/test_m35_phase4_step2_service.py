import json
import tempfile
from datetime import date
from pathlib import Path

from trading_ai.scanner.option_surface_analytics.policy import (
    OptionSurfaceAnalyticsPolicy,
)
from trading_ai.scanner.option_surface_analytics.service import (
    OptionSurfaceAnalyticsService,
)


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "features.jsonl"

        records = []
        for option_type, strike, delta, iv in (
            ("PUT", 180, 0.25, 0.32),
            ("PUT", 190, 0.50, 0.28),
            ("CALL", 200, 0.50, 0.27),
            ("CALL", 210, 0.25, 0.29),
        ):
            records.append(
                {
                    "underlying_symbol": "AAPL",
                    "quote_date": "2026-07-20",
                    "expiry": "2026-08-21",
                    "option_type": option_type,
                    "strike": strike,
                    "days_to_expiration": 32,
                    "implied_volatility": iv,
                    "absolute_delta": delta,
                    "volume": 20,
                    "open_interest": 100,
                    "governance_status": "READY",
                }
            )

        with source.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record) + "\n")

        policy = OptionSurfaceAnalyticsPolicy(
            minimum_contracts_per_expiration=4,
            minimum_strikes_per_expiration=3,
            minimum_open_interest_per_expiration=100,
            minimum_atm_term_points_for_ready=1,
        )
        profile = OptionSurfaceAnalyticsService(policy).run(
            as_of_date=date(2026, 7, 20),
            feature_input_path=source,
            expiration_output_path=root / "expirations.jsonl",
            symbol_output_path=root / "symbols.jsonl",
        )

        assert profile.contracts_read == 4
        assert profile.contracts_eligible == 4
        assert profile.expirations_evaluated == 1
        assert profile.symbols_evaluated == 1
        assert (root / "expirations.jsonl").exists()
        assert (root / "symbols.jsonl").exists()

    print("Milestone 35 Phase 4 Step 2 service assertions passed.")


if __name__ == "__main__":
    main()
