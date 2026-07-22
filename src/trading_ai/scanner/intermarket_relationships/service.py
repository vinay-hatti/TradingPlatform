from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from .contracts import IntermarketRunProfile
from .engine import IntermarketRelationshipEngine
from .policy import IntermarketRelationshipPolicy
from .serialization import load_jsonl, write_json_atomic


class IntermarketRelationshipService:
    def __init__(
        self,
        policy: IntermarketRelationshipPolicy | None = None,
    ) -> None:
        self.policy = policy or IntermarketRelationshipPolicy()
        self.engine = IntermarketRelationshipEngine(self.policy)

    def run(
        self,
        *,
        as_of_date: date,
        input_path: str | Path,
        output_path: str | Path,
    ) -> IntermarketRunProfile:
        records = load_jsonl(input_path)

        features_by_symbol = {
            str(record["symbol"]).strip().upper(): record
            for record in records
            if record.get("symbol")
        }

        profile = self.engine.evaluate(
            as_of_date=as_of_date,
            features_by_symbol=features_by_symbol,
        )

        write_json_atomic(output_path, profile)

        required_symbols = {
            "SPY", "QQQ", "IWM", "^VIX", "IEF", "TLT",
            "LQD", "HYG", "UUP", "GLD", "USO",
        }
        available_symbols = required_symbols & set(features_by_symbol)

        return IntermarketRunProfile(
            as_of_date=as_of_date,
            generated_at=datetime.now(timezone.utc),
            input_path=str(input_path),
            output_path=str(output_path),
            records_read=len(records),
            symbols_available=len(available_symbols),
            symbols_missing=len(required_symbols - available_symbols),
            market_state=profile.market_state,
            confidence=profile.confidence,
            governance_status=profile.governance_status.value,
            metadata={
                "feature_version": profile.feature_version,
                "required_symbols": sorted(required_symbols),
                "available_symbols": sorted(available_symbols),
                "missing_symbols": sorted(required_symbols - available_symbols),
                "policy": self.policy.__dict__.copy(),
            },
        )
