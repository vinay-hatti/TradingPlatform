from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from .contracts import (
    AggregateGovernanceStatus,
    OptionSurfaceRunProfile,
)
from .engine import (
    OptionFeatureInput,
    OptionSurfaceAnalyticsEngine,
)
from .policy import OptionSurfaceAnalyticsPolicy
from .serialization import write_jsonl_atomic


class OptionSurfaceAnalyticsService:
    def __init__(
        self,
        policy: OptionSurfaceAnalyticsPolicy | None = None,
    ) -> None:
        self.policy = policy or OptionSurfaceAnalyticsPolicy()
        self.engine = OptionSurfaceAnalyticsEngine(self.policy)

    def run(
        self,
        *,
        as_of_date: date,
        feature_input_path: str | Path,
        expiration_output_path: str | Path,
        symbol_output_path: str | Path,
    ) -> OptionSurfaceRunProfile:
        rows = self._load_features(feature_input_path)

        mismatched = [
            row
            for row in rows
            if row.quote_date != as_of_date
        ]
        if mismatched:
            raise ValueError(
                f"{len(mismatched)} feature records do not match "
                f"as-of date {as_of_date.isoformat()}"
            )

        expirations, symbols = self.engine.build(rows)
        write_jsonl_atomic(expiration_output_path, expirations)
        write_jsonl_atomic(symbol_output_path, symbols)

        allowed = self.policy.normalized_allowed_statuses()
        eligible_contracts = sum(
            str(row.governance_status).strip().upper() in allowed
            for row in rows
        )

        return OptionSurfaceRunProfile(
            as_of_date=as_of_date,
            generated_at=datetime.now(timezone.utc),
            input_path=str(feature_input_path),
            expiration_output_path=str(expiration_output_path),
            symbol_output_path=str(symbol_output_path),
            contracts_read=len(rows),
            contracts_eligible=eligible_contracts,
            contracts_excluded=len(rows) - eligible_contracts,
            symbols_evaluated=len(symbols),
            expirations_evaluated=len(expirations),
            expiration_ready=sum(
                r.governance_status
                == AggregateGovernanceStatus.READY
                for r in expirations
            ),
            expiration_review=sum(
                r.governance_status
                == AggregateGovernanceStatus.REVIEW
                for r in expirations
            ),
            expiration_excluded=sum(
                r.governance_status
                == AggregateGovernanceStatus.EXCLUDED
                for r in expirations
            ),
            symbol_ready=sum(
                r.governance_status
                == AggregateGovernanceStatus.READY
                for r in symbols
            ),
            symbol_review=sum(
                r.governance_status
                == AggregateGovernanceStatus.REVIEW
                for r in symbols
            ),
            symbol_excluded=sum(
                r.governance_status
                == AggregateGovernanceStatus.EXCLUDED
                for r in symbols
            ),
            metadata={
                "policy": self.policy.__dict__.copy(),
            },
        )

    @staticmethod
    def _load_features(
        path: str | Path,
    ) -> tuple[OptionFeatureInput, ...]:
        input_path = Path(path)
        if not input_path.exists():
            raise FileNotFoundError(input_path)

        rows = []
        with input_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    item = json.loads(stripped)
                    rows.append(
                        OptionFeatureInput(
                            underlying_symbol=str(
                                item["underlying_symbol"]
                            ),
                            quote_date=date.fromisoformat(
                                item["quote_date"]
                            ),
                            expiry=date.fromisoformat(item["expiry"]),
                            option_type=str(item["option_type"]),
                            strike=float(item["strike"]),
                            days_to_expiration=int(
                                item["days_to_expiration"]
                            ),
                            implied_volatility=(
                                None
                                if item.get("implied_volatility") is None
                                else float(
                                    item["implied_volatility"]
                                )
                            ),
                            absolute_delta=(
                                None
                                if item.get("absolute_delta") is None
                                else float(item["absolute_delta"])
                            ),
                            volume=(
                                None
                                if item.get("volume") is None
                                else int(item["volume"])
                            ),
                            open_interest=(
                                None
                                if item.get("open_interest") is None
                                else int(item["open_interest"])
                            ),
                            governance_status=str(
                                item["governance_status"]
                            ),
                        )
                    )
                except Exception as exc:
                    raise ValueError(
                        f"invalid feature record at line "
                        f"{line_number}: {exc}"
                    ) from exc
        return tuple(rows)
