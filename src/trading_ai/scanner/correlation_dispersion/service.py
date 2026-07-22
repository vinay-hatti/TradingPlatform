from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import CorrelationDispersionRunProfile
from .engine import CorrelationDispersionEngine
from .policy import CorrelationDispersionPolicy
from .serialization import load_jsonl, write_json_atomic


class CorrelationDispersionService:
    def __init__(
        self,
        policy: CorrelationDispersionPolicy | None = None,
    ) -> None:
        self.policy = policy or CorrelationDispersionPolicy()
        self.engine = CorrelationDispersionEngine(self.policy)

    def run(
        self,
        *,
        as_of_date: date,
        input_path: str | Path,
        history_path: str | Path,
        output_path: str | Path,
    ) -> CorrelationDispersionRunProfile:
        feature_records = load_jsonl(input_path)
        history_records = load_jsonl(history_path)

        features_by_symbol = {
            str(record["symbol"]).strip().upper(): record
            for record in feature_records
            if record.get("symbol")
        }

        return_history_by_symbol: dict[str, list[float]] = {}
        for record in history_records:
            symbol = str(record.get("symbol", "")).strip().upper()
            returns = record.get("returns")
            if not symbol or not isinstance(returns, list):
                continue
            return_history_by_symbol[symbol] = [
                float(value)
                for value in returns
                if value is not None
            ]

        profile = self.engine.evaluate(
            as_of_date=as_of_date,
            features_by_symbol=features_by_symbol,
            return_history_by_symbol=return_history_by_symbol,
        )

        write_json_atomic(output_path, profile)

        return CorrelationDispersionRunProfile(
            as_of_date=as_of_date,
            generated_at=datetime.now(timezone.utc),
            input_path=str(input_path),
            output_path=str(output_path),
            records_read=len(feature_records),
            symbols_available=profile.governed_symbol_count,
            pair_count=profile.pair_count,
            correlation_regime=profile.correlation_regime,
            dispersion_regime=profile.dispersion_regime,
            market_structure_state=profile.market_structure_state,
            confidence=profile.confidence,
            governance_status=profile.governance_status.value,
            metadata={
                "feature_version": profile.feature_version,
                "history_path": str(history_path),
                "correlation_breakdown_count": (
                    profile.correlation_breakdown_count
                ),
                "correlation_breakdown_ratio": (
                    profile.correlation_breakdown_ratio
                ),
                "diversification_score": (
                    profile.diversification_score
                ),
                "policy": self.policy.__dict__.copy(),
            },
        )
