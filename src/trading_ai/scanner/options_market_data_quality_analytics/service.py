from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import GovernanceStatus, OptionChainQualityRunProfile
from .engine import OptionChainQualityEngine, OptionContractQualityRow
from .policy import OptionChainQualityPolicy


class OptionChainQualityService:
    SOURCE_TABLE = "option_contract_history"

    def __init__(
        self,
        session: Session,
        *,
        policy: OptionChainQualityPolicy | None = None,
    ) -> None:
        self.session = session
        self.policy = policy or OptionChainQualityPolicy()
        self.engine = OptionChainQualityEngine(self.policy)

    def run(
        self,
        *,
        as_of_date: date,
        expected_symbols: Sequence[str] | None = None,
    ) -> OptionChainQualityRunProfile:
        rows = self._load_rows(as_of_date)
        profiles = self.engine.evaluate(
            rows,
            quote_date=as_of_date,
            expected_symbols=expected_symbols,
        )
        scores = [item.overall_quality_score for item in profiles]
        quoted_contracts = sum(
            1 for row in rows if row.bid is not None and row.ask is not None
        )

        return OptionChainQualityRunProfile(
            as_of_date=as_of_date,
            generated_at=datetime.now(timezone.utc),
            source_table=self.SOURCE_TABLE,
            symbols_evaluated=len(profiles),
            ready_symbols=sum(
                p.governance_status == GovernanceStatus.READY for p in profiles
            ),
            review_symbols=sum(
                p.governance_status == GovernanceStatus.REVIEW for p in profiles
            ),
            failed_symbols=sum(
                p.governance_status == GovernanceStatus.FAILED for p in profiles
            ),
            average_quality_score=(
                round(sum(scores) / len(scores), 6) if scores else 0.0
            ),
            minimum_quality_score=round(min(scores), 6) if scores else 0.0,
            maximum_quality_score=round(max(scores), 6) if scores else 0.0,
            quote_data_observed=quoted_contracts > 0,
            quoted_contracts=quoted_contracts,
            total_contracts=len(rows),
            profiles=profiles,
            metadata={
                "policy": self.policy.__dict__.copy(),
                "expected_symbol_count": (
                    len(expected_symbols) if expected_symbols is not None else None
                ),
                "scoring_mode": (
                    "FULL"
                    if quoted_contracts > 0
                    else "PROVIDER_AWARE_WITHOUT_NBBO"
                ),
            },
        )

    def _load_rows(self, as_of_date: date):
        statement = text(
            f"""
            SELECT underlying_symbol, quote_date, bid, ask, last, volume,
                   open_interest, implied_volatility, delta, gamma, theta, vega
            FROM {self.SOURCE_TABLE}
            WHERE quote_date = :as_of_date
            ORDER BY underlying_symbol, expiry, strike, option_type
            """
        )
        result = self.session.execute(
            statement, {"as_of_date": as_of_date}
        ).mappings()

        return tuple(
            OptionContractQualityRow(
                underlying_symbol=str(r["underlying_symbol"]),
                quote_date=r["quote_date"],
                bid=self._float_or_none(r["bid"]),
                ask=self._float_or_none(r["ask"]),
                last=self._float_or_none(r["last"]),
                volume=self._int_or_none(r["volume"]),
                open_interest=self._int_or_none(r["open_interest"]),
                implied_volatility=self._float_or_none(r["implied_volatility"]),
                delta=self._float_or_none(r["delta"]),
                gamma=self._float_or_none(r["gamma"]),
                theta=self._float_or_none(r["theta"]),
                vega=self._float_or_none(r["vega"]),
            )
            for r in result
        )

    @staticmethod
    def load_expected_symbols(csv_path: str | Path):
        path = Path(csv_path)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            names = {
                n.strip().lower(): n for n in (reader.fieldnames or []) if n
            }
            column = (
                names.get("symbol")
                or names.get("ticker")
                or names.get("underlying_symbol")
            )
            if column is None:
                raise ValueError(
                    f"{path} must contain symbol, ticker, or underlying_symbol"
                )
            return tuple(sorted({
                str(row.get(column, "")).strip().upper()
                for row in reader
                if str(row.get(column, "")).strip()
            }))

    @staticmethod
    def _float_or_none(value):
        return None if value is None else float(value)

    @staticmethod
    def _int_or_none(value):
        return None if value is None else int(value)
