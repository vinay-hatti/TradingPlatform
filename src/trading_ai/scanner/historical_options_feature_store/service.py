from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .contracts import (
    FeatureGovernanceStatus,
    HistoricalOptionFeatureRunProfile,
)
from .engine import (
    HistoricalOptionFeatureEngine,
    HistoricalOptionInput,
)
from .policy import HistoricalOptionFeaturePolicy
from .serialization import write_feature_jsonl_atomic


class HistoricalOptionFeatureService:
    SOURCE_TABLE = "option_contract_history"
    PRICE_HISTORY_TABLE = "price_history"

    OPTION_PRICE_COLUMN_CANDIDATES = (
        "underlying_price",
        "underlying_close",
        "underlying_last",
        "underlying_last_price",
        "stock_price",
        "spot_price",
    )

    PRICE_HISTORY_PRICE_COLUMN_CANDIDATES = (
        "close",
        "adjusted_close",
        "adj_close",
        "last",
    )

    PRICE_HISTORY_SYMBOL_COLUMN_CANDIDATES = (
        "symbol",
        "underlying_symbol",
        "ticker",
    )

    PRICE_HISTORY_DATE_COLUMN_CANDIDATES = (
        "date",
        "quote_date",
        "trade_date",
        "as_of_date",
    )

    def __init__(
        self,
        session: Session,
        *,
        policy: HistoricalOptionFeaturePolicy | None = None,
    ) -> None:
        self.session = session
        self.policy = policy or HistoricalOptionFeaturePolicy()
        self.engine = HistoricalOptionFeatureEngine(self.policy)
        self._underlying_price_source = "unresolved"

    def run(
        self,
        *,
        as_of_date: date,
        readiness_report_path: str | Path,
        output_path: str | Path,
    ) -> HistoricalOptionFeatureRunProfile:
        readiness = self._load_readiness(readiness_report_path)

        report_date = readiness.get("as_of_date")
        if report_date and report_date != as_of_date.isoformat():
            raise ValueError(
                f"readiness report date {report_date!r} does not match "
                f"{as_of_date.isoformat()!r}"
            )

        readiness_by_symbol = {
            str(item["symbol"]).strip().upper(): str(
                item["readiness_status"]
            ).strip().upper()
            for item in readiness.get("profiles", ())
        }

        rows = self._load_rows(
            as_of_date=as_of_date,
            readiness_by_symbol=readiness_by_symbol,
        )
        records = self.engine.build(rows)
        write_feature_jsonl_atomic(output_path, records)

        considered = set(readiness_by_symbol)
        included = {
            record.underlying_symbol
            for record in records
            if record.governance_status
            != FeatureGovernanceStatus.EXCLUDED
        }

        records_with_underlying_features = sum(
            record.moneyness is not None for record in records
        )

        return HistoricalOptionFeatureRunProfile(
            as_of_date=as_of_date,
            generated_at=datetime.now(timezone.utc),
            symbols_considered=len(considered),
            symbols_included=len(included),
            symbols_excluded=len(considered - included),
            contracts_read=len(rows),
            features_generated=len(records),
            records_ready=sum(
                record.governance_status
                == FeatureGovernanceStatus.READY
                for record in records
            ),
            records_review=sum(
                record.governance_status
                == FeatureGovernanceStatus.REVIEW
                for record in records
            ),
            records_excluded=sum(
                record.governance_status
                == FeatureGovernanceStatus.EXCLUDED
                for record in records
            ),
            output_path=str(output_path),
            metadata={
                "source_table": self.SOURCE_TABLE,
                "policy": self.policy.__dict__.copy(),
                "readiness_report_path": str(readiness_report_path),
                "underlying_price_source": self._underlying_price_source,
                "records_with_underlying_price_features": (
                    records_with_underlying_features
                ),
                "records_without_underlying_price_features": (
                    len(records) - records_with_underlying_features
                ),
            },
        )

    def _load_rows(
        self,
        *,
        as_of_date: date,
        readiness_by_symbol: dict[str, str],
    ) -> tuple[HistoricalOptionInput, ...]:
        statement = self._build_source_statement()

        result = self.session.execute(
            statement,
            {"as_of_date": as_of_date},
        ).mappings()

        rows: list[HistoricalOptionInput] = []
        for item in result:
            symbol = str(item["underlying_symbol"]).strip().upper()
            rows.append(
                HistoricalOptionInput(
                    underlying_symbol=symbol,
                    quote_date=item["quote_date"],
                    expiry=item["expiry"],
                    option_type=str(item["option_type"]),
                    strike=float(item["strike"]),
                    underlying_price=self._float_or_none(
                        item["underlying_price"]
                    ),
                    last_price=self._float_or_none(item["last"]),
                    volume=self._int_or_none(item["volume"]),
                    open_interest=self._int_or_none(
                        item["open_interest"]
                    ),
                    implied_volatility=self._float_or_none(
                        item["implied_volatility"]
                    ),
                    delta=self._float_or_none(item["delta"]),
                    gamma=self._float_or_none(item["gamma"]),
                    theta=self._float_or_none(item["theta"]),
                    vega=self._float_or_none(item["vega"]),
                    readiness_status=readiness_by_symbol.get(
                        symbol,
                        "FAILED",
                    ),
                )
            )

        return tuple(rows)

    def _build_source_statement(self):
        inspector = inspect(self.session.get_bind())

        option_columns = self._column_names(
            inspector,
            self.SOURCE_TABLE,
        )
        if not option_columns:
            raise RuntimeError(
                f"required table {self.SOURCE_TABLE!r} was not found"
            )

        option_price_column = self._first_present(
            self.OPTION_PRICE_COLUMN_CANDIDATES,
            option_columns,
        )

        if option_price_column:
            self._underlying_price_source = (
                f"{self.SOURCE_TABLE}.{option_price_column}"
            )
            underlying_expression = (
                f'oc."{option_price_column}" AS underlying_price'
            )
            join_clause = ""
        else:
            price_columns = self._column_names(
                inspector,
                self.PRICE_HISTORY_TABLE,
            )
            price_column = self._first_present(
                self.PRICE_HISTORY_PRICE_COLUMN_CANDIDATES,
                price_columns,
            )
            symbol_column = self._first_present(
                self.PRICE_HISTORY_SYMBOL_COLUMN_CANDIDATES,
                price_columns,
            )
            date_column = self._first_present(
                self.PRICE_HISTORY_DATE_COLUMN_CANDIDATES,
                price_columns,
            )

            if price_column and symbol_column and date_column:
                self._underlying_price_source = (
                    f"{self.PRICE_HISTORY_TABLE}.{price_column}"
                )
                underlying_expression = (
                    f'ph."{price_column}" AS underlying_price'
                )
                join_clause = (
                    f'LEFT JOIN "{self.PRICE_HISTORY_TABLE}" ph '
                    f'ON UPPER(ph."{symbol_column}") = '
                    f'UPPER(oc.underlying_symbol) '
                    f'AND ph."{date_column}" = oc.quote_date'
                )
            else:
                self._underlying_price_source = "not_available"
                underlying_expression = (
                    "CAST(NULL AS DOUBLE PRECISION) AS underlying_price"
                )
                join_clause = ""

        return text(
            f'''
            SELECT
                oc.underlying_symbol,
                oc.quote_date,
                oc.expiry,
                oc.option_type,
                oc.strike,
                {underlying_expression},
                oc.last,
                oc.volume,
                oc.open_interest,
                oc.implied_volatility,
                oc.delta,
                oc.gamma,
                oc.theta,
                oc.vega
            FROM "{self.SOURCE_TABLE}" oc
            {join_clause}
            WHERE oc.quote_date = :as_of_date
            ORDER BY
                oc.underlying_symbol,
                oc.expiry,
                oc.strike,
                oc.option_type
            '''
        )

    @staticmethod
    def _column_names(inspector, table_name: str) -> set[str]:
        try:
            return {
                str(column["name"]).strip().lower()
                for column in inspector.get_columns(table_name)
            }
        except Exception:
            return set()

    @staticmethod
    def _first_present(
        candidates: tuple[str, ...],
        available: set[str],
    ) -> str | None:
        for candidate in candidates:
            if candidate.lower() in available:
                return candidate
        return None

    @staticmethod
    def _load_readiness(path: str | Path) -> dict:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)

        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        if not isinstance(payload, dict):
            raise ValueError(
                "readiness report must contain a JSON object"
            )
        return payload

    @staticmethod
    def _float_or_none(value):
        return None if value is None else float(value)

    @staticmethod
    def _int_or_none(value):
        return None if value is None else int(value)
