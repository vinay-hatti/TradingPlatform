from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import (
    GovernanceStatus,
    OptionChainCoverageRunProfile,
)
from .engine import OptionChainCoverageEngine, OptionContractCoverageRow
from .policy import OptionChainCoveragePolicy


class OptionChainCoverageService:
    SOURCE_TABLE = "option_contract_history"

    def __init__(
        self,
        session: Session,
        *,
        policy: OptionChainCoveragePolicy | None = None,
    ) -> None:
        self.session = session
        self.policy = policy or OptionChainCoveragePolicy()
        self.engine = OptionChainCoverageEngine(self.policy)

    def run(
        self,
        *,
        as_of_date: date,
        expected_symbols: Sequence[str] | None = None,
    ) -> OptionChainCoverageRunProfile:
        rows = self._load_rows(as_of_date)
        profiles = self.engine.evaluate(
            rows,
            quote_date=as_of_date,
            expected_symbols=expected_symbols,
        )

        scores = [profile.overall_coverage_score for profile in profiles]
        ready = sum(
            profile.governance_status == GovernanceStatus.READY
            for profile in profiles
        )
        review = sum(
            profile.governance_status == GovernanceStatus.REVIEW
            for profile in profiles
        )
        failed = sum(
            profile.governance_status == GovernanceStatus.FAILED
            for profile in profiles
        )

        return OptionChainCoverageRunProfile(
            as_of_date=as_of_date,
            generated_at=datetime.now(timezone.utc),
            source_table=self.SOURCE_TABLE,
            symbols_evaluated=len(profiles),
            ready_symbols=ready,
            review_symbols=review,
            failed_symbols=failed,
            average_coverage_score=(
                round(sum(scores) / len(scores), 6) if scores else 0.0
            ),
            minimum_coverage_score=round(min(scores), 6) if scores else 0.0,
            maximum_coverage_score=round(max(scores), 6) if scores else 0.0,
            profiles=profiles,
            metadata={
                "policy": self.policy.__dict__.copy(),
                "expected_symbol_count": (
                    len(expected_symbols) if expected_symbols is not None else None
                ),
            },
        )

    def _load_rows(
        self,
        as_of_date: date,
    ) -> tuple[OptionContractCoverageRow, ...]:
        statement = text(
            f"""
            SELECT
                underlying_symbol,
                quote_date,
                expiry,
                option_type,
                strike
            FROM {self.SOURCE_TABLE}
            WHERE quote_date = :as_of_date
            ORDER BY underlying_symbol, expiry, strike, option_type
            """
        )

        result = self.session.execute(
            statement,
            {"as_of_date": as_of_date},
        ).mappings()

        return tuple(
            OptionContractCoverageRow(
                underlying_symbol=str(row["underlying_symbol"]),
                quote_date=row["quote_date"],
                expiry=row["expiry"],
                option_type=str(row["option_type"]),
                strike=float(row["strike"]),
            )
            for row in result
        )

    @staticmethod
    def load_expected_symbols(
        csv_path: str | Path,
    ) -> tuple[str, ...]:
        path = Path(csv_path)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return ()

            normalized = {
                name.strip().lower(): name
                for name in reader.fieldnames
                if name
            }
            symbol_column = (
                normalized.get("symbol")
                or normalized.get("ticker")
                or normalized.get("underlying_symbol")
            )
            if symbol_column is None:
                raise ValueError(
                    f"{path} must contain symbol, ticker, or underlying_symbol"
                )

            symbols = {
                str(row.get(symbol_column, "")).strip().upper()
                for row in reader
                if str(row.get(symbol_column, "")).strip()
            }

        return tuple(sorted(symbols))
