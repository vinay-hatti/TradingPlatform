from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import (
    SurfacePersistencePolicy,
    SurfacePersistenceRunProfile,
)
from .serialization import write_csv_atomic, write_json_atomic


class OptionSurfacePersistenceService:
    EXPIRATION_FIELDS = [
        "underlying_symbol",
        "quote_date",
        "expiry",
        "days_to_expiration",
        "contract_count",
        "call_contract_count",
        "put_contract_count",
        "strike_count",
        "total_volume",
        "total_open_interest",
        "call_volume",
        "put_volume",
        "call_open_interest",
        "put_open_interest",
        "call_put_volume_ratio",
        "call_put_open_interest_ratio",
        "weighted_implied_volatility",
        "call_weighted_implied_volatility",
        "put_weighted_implied_volatility",
        "atm_implied_volatility",
        "downside_put_implied_volatility",
        "upside_call_implied_volatility",
        "put_skew_25d_minus_atm",
        "call_skew_25d_minus_atm",
        "risk_reversal_25d",
        "near_money_contract_count",
        "downside_put_contract_count",
        "upside_call_contract_count",
        "top_5_open_interest_concentration",
        "top_5_volume_concentration",
        "governance_status",
        "governance_reasons",
    ]

    SYMBOL_FIELDS = [
        "underlying_symbol",
        "quote_date",
        "expiration_count",
        "ready_expiration_count",
        "review_expiration_count",
        "excluded_expiration_count",
        "nearest_expiry",
        "farthest_expiry",
        "nearest_atm_implied_volatility",
        "farthest_atm_implied_volatility",
        "atm_term_structure_slope",
        "total_contract_count",
        "total_volume",
        "total_open_interest",
        "aggregate_put_call_volume_ratio",
        "aggregate_put_call_open_interest_ratio",
        "governance_status",
        "governance_reasons",
    ]

    def __init__(
        self,
        policy: SurfacePersistencePolicy | None = None,
    ) -> None:
        self.policy = policy or SurfacePersistencePolicy()

    def run(
        self,
        *,
        as_of_date: date,
        expiration_input_path: str | Path,
        symbol_input_path: str | Path,
        expiration_csv_path: str | Path,
        symbol_csv_path: str | Path,
        governance_summary_path: str | Path,
    ) -> SurfacePersistenceRunProfile:
        expirations = self._load_jsonl(expiration_input_path)
        symbols = self._load_jsonl(symbol_input_path)

        if self.policy.require_matching_as_of_date:
            self._validate_dates(
                as_of_date,
                expirations,
                "expiration",
            )
            self._validate_dates(
                as_of_date,
                symbols,
                "symbol",
            )

        duplicate_expiration_keys = self._duplicate_count(
            expirations,
            ("underlying_symbol", "quote_date", "expiry"),
        )
        duplicate_symbol_keys = self._duplicate_count(
            symbols,
            ("underlying_symbol", "quote_date"),
        )

        if (
            duplicate_expiration_keys
            and self.policy.fail_on_duplicate_expiration_key
        ):
            raise ValueError(
                f"found {duplicate_expiration_keys} duplicate "
                "expiration surface keys"
            )
        if (
            duplicate_symbol_keys
            and self.policy.fail_on_duplicate_symbol_key
        ):
            raise ValueError(
                f"found {duplicate_symbol_keys} duplicate symbol "
                "surface keys"
            )

        allowed_expiration = {
            value.strip().upper()
            for value in self.policy.allowed_expiration_statuses
        }
        allowed_symbol = {
            value.strip().upper()
            for value in self.policy.allowed_symbol_statuses
        }

        persisted_expirations = [
            row
            for row in expirations
            if str(row.get("governance_status", "")).strip().upper()
            in allowed_expiration
        ]
        persisted_symbols = [
            row
            for row in symbols
            if str(row.get("governance_status", "")).strip().upper()
            in allowed_symbol
        ]

        write_csv_atomic(
            expiration_csv_path,
            persisted_expirations,
            fieldnames=self.EXPIRATION_FIELDS,
        )
        write_csv_atomic(
            symbol_csv_path,
            persisted_symbols,
            fieldnames=self.SYMBOL_FIELDS,
        )

        expiration_counts = Counter(
            str(row.get("governance_status", "UNKNOWN")).upper()
            for row in expirations
        )
        symbol_counts = Counter(
            str(row.get("governance_status", "UNKNOWN")).upper()
            for row in symbols
        )

        summary = {
            "as_of_date": as_of_date.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "expiration_surfaces": {
                "read": len(expirations),
                "persisted": len(persisted_expirations),
                "filtered": len(expirations) - len(persisted_expirations),
                "status_counts": dict(sorted(expiration_counts.items())),
                "duplicate_keys": duplicate_expiration_keys,
            },
            "symbol_surfaces": {
                "read": len(symbols),
                "persisted": len(persisted_symbols),
                "filtered": len(symbols) - len(persisted_symbols),
                "status_counts": dict(sorted(symbol_counts.items())),
                "duplicate_keys": duplicate_symbol_keys,
            },
            "policy": {
                "allowed_expiration_statuses": list(
                    self.policy.allowed_expiration_statuses
                ),
                "allowed_symbol_statuses": list(
                    self.policy.allowed_symbol_statuses
                ),
                "require_matching_as_of_date": (
                    self.policy.require_matching_as_of_date
                ),
                "fail_on_duplicate_expiration_key": (
                    self.policy.fail_on_duplicate_expiration_key
                ),
                "fail_on_duplicate_symbol_key": (
                    self.policy.fail_on_duplicate_symbol_key
                ),
            },
        }
        write_json_atomic(governance_summary_path, summary)

        return SurfacePersistenceRunProfile(
            as_of_date=as_of_date,
            generated_at=datetime.now(timezone.utc),
            expiration_input_path=str(expiration_input_path),
            symbol_input_path=str(symbol_input_path),
            expiration_csv_path=str(expiration_csv_path),
            symbol_csv_path=str(symbol_csv_path),
            governance_summary_path=str(governance_summary_path),
            expiration_records_read=len(expirations),
            expiration_records_persisted=len(persisted_expirations),
            expiration_records_filtered=(
                len(expirations) - len(persisted_expirations)
            ),
            symbol_records_read=len(symbols),
            symbol_records_persisted=len(persisted_symbols),
            symbol_records_filtered=(
                len(symbols) - len(persisted_symbols)
            ),
            duplicate_expiration_keys=duplicate_expiration_keys,
            duplicate_symbol_keys=duplicate_symbol_keys,
            expiration_ready=expiration_counts.get("READY", 0),
            expiration_review=expiration_counts.get("REVIEW", 0),
            expiration_excluded=expiration_counts.get("EXCLUDED", 0),
            symbol_ready=symbol_counts.get("READY", 0),
            symbol_review=symbol_counts.get("REVIEW", 0),
            symbol_excluded=symbol_counts.get("EXCLUDED", 0),
            metadata={
                "expiration_fields": self.EXPIRATION_FIELDS,
                "symbol_fields": self.SYMBOL_FIELDS,
            },
        )

    @staticmethod
    def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
        source = Path(path)
        if not source.exists():
            raise FileNotFoundError(source)

        rows: list[dict[str, Any]] = []
        with source.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    value = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"invalid JSON at {source}:{line_number}: {exc}"
                    ) from exc
                if not isinstance(value, dict):
                    raise ValueError(
                        f"expected object at {source}:{line_number}"
                    )
                rows.append(value)
        return rows

    @staticmethod
    def _validate_dates(
        as_of_date: date,
        rows: list[dict[str, Any]],
        label: str,
    ) -> None:
        expected = as_of_date.isoformat()
        mismatched = [
            row
            for row in rows
            if str(row.get("quote_date")) != expected
        ]
        if mismatched:
            raise ValueError(
                f"{len(mismatched)} {label} records do not match "
                f"as-of date {expected}"
            )

    @staticmethod
    def _duplicate_count(
        rows: list[dict[str, Any]],
        key_fields: tuple[str, ...],
    ) -> int:
        counts = Counter(
            tuple(row.get(field) for field in key_fields)
            for row in rows
        )
        return sum(count - 1 for count in counts.values() if count > 1)
