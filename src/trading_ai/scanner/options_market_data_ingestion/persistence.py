from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from trading_ai.scanner.options_market_data_quality.contracts import (
    OptionQuoteRecord,
)


@dataclass(frozen=True)
class WriteResult:
    inserted_records: int
    updated_records: int
    skipped_records: int


class OptionHistoryWriter:
    """Persist partial option snapshots while requiring canonical identity."""

    TABLE_NAME = "option_contract_history"

    REQUIRED_FIELDS = (
        "underlying_symbol",
        "option_symbol",
        "quote_date",
        "expiry",
        "option_type",
        "strike",
    )

    SUPPORTED_FIELDS = (
        "underlying_symbol",
        "option_symbol",
        "quote_date",
        "expiry",
        "option_type",
        "strike",
        "bid",
        "ask",
        "last",
        "volume",
        "open_interest",
        "implied_volatility",
        "delta",
        "gamma",
        "theta",
        "vega",
    )

    def __init__(self, database: Session | Engine) -> None:
        self.database = database

    def write(self, records: Sequence[OptionQuoteRecord]) -> WriteResult:
        if not records:
            return WriteResult(0, 0, 0)

        columns = self._table_columns()
        accepted, rejected = self._filter_identity_complete(records, columns)

        if not accepted:
            return WriteResult(0, 0, rejected)

        conflict_columns = self._select_conflict_columns(
            has_option_symbol="option_symbol" in columns
        )

        if self._dialect_name() == "postgresql" and conflict_columns:
            result = self._write_postgresql_upsert(
                accepted,
                columns=columns,
                conflict_columns=conflict_columns,
            )
        else:
            result = self._write_update_then_insert(
                accepted,
                columns=columns,
                key_columns=(
                    ("option_symbol", "quote_date")
                    if "option_symbol" in columns
                    else (
                        "underlying_symbol",
                        "expiry",
                        "quote_date",
                        "strike",
                        "option_type",
                    )
                ),
            )

        return WriteResult(
            result.inserted_records,
            result.updated_records,
            result.skipped_records + rejected,
        )

    def _filter_identity_complete(
        self,
        records: Sequence[OptionQuoteRecord],
        columns: set[str],
    ) -> tuple[tuple[OptionQuoteRecord, ...], int]:
        required = tuple(field for field in self.REQUIRED_FIELDS if field in columns)
        accepted = []
        rejected = 0

        for record in records:
            params = self._all_params(record)
            missing = [
                field
                for field in required
                if params.get(field) is None
                or (
                    isinstance(params.get(field), str)
                    and not str(params.get(field)).strip()
                )
            ]
            if missing:
                rejected += 1
            else:
                accepted.append(record)

        return tuple(accepted), rejected

    def _write_postgresql_upsert(
        self,
        records: Sequence[OptionQuoteRecord],
        *,
        columns: set[str],
        conflict_columns: tuple[str, ...],
    ) -> WriteResult:
        insert_columns = self._insert_columns(columns)
        update_columns = tuple(
            column
            for column in insert_columns
            if column not in conflict_columns and column not in {"id", "created_at"}
        )

        statement = text(
            f"""
            INSERT INTO {self.TABLE_NAME} (
                {", ".join(insert_columns)}
            ) VALUES (
                {", ".join(f":{column}" for column in insert_columns)}
            )
            ON CONFLICT ({", ".join(conflict_columns)})
            DO UPDATE SET
                {", ".join(f"{column} = EXCLUDED.{column}" for column in update_columns)}
            """
        )

        self._execute_many(
            statement,
            [self._params(record, columns) for record in records],
        )
        return WriteResult(len(records), 0, 0)

    def _write_update_then_insert(
        self,
        records: Sequence[OptionQuoteRecord],
        *,
        columns: set[str],
        key_columns: tuple[str, ...],
    ) -> WriteResult:
        insert_columns = self._insert_columns(columns)
        update_columns = tuple(
            column
            for column in insert_columns
            if column not in key_columns and column not in {"id", "created_at"}
        )

        where_sql = " AND ".join(f"{column} = :{column}" for column in key_columns)
        select_statement = text(
            f"SELECT COUNT(*) FROM {self.TABLE_NAME} WHERE {where_sql}"
        )
        update_statement = text(
            f"""
            UPDATE {self.TABLE_NAME}
            SET {", ".join(f"{column} = :{column}" for column in update_columns)}
            WHERE {where_sql}
            """
        )
        insert_statement = text(
            f"""
            INSERT INTO {self.TABLE_NAME} ({", ".join(insert_columns)})
            VALUES ({", ".join(f":{column}" for column in insert_columns)})
            """
        )

        inserted = 0
        updated = 0

        def apply(connection) -> None:
            nonlocal inserted, updated
            for record in records:
                params = self._params(record, columns)
                exists = connection.execute(select_statement, params).scalar_one()
                if exists:
                    connection.execute(update_statement, params)
                    updated += 1
                else:
                    connection.execute(insert_statement, params)
                    inserted += 1

        if isinstance(self.database, Engine):
            with self.database.begin() as connection:
                apply(connection)
        else:
            apply(self.database)
            self.database.commit()

        return WriteResult(inserted, updated, 0)

    def _select_conflict_columns(
        self,
        *,
        has_option_symbol: bool,
    ) -> tuple[str, ...] | None:
        inspector = inspect(self._bind())
        candidates = []

        pk = tuple(
            inspector.get_pk_constraint(self.TABLE_NAME).get(
                "constrained_columns"
            ) or ()
        )
        if pk:
            candidates.append(pk)

        for constraint in inspector.get_unique_constraints(self.TABLE_NAME):
            cols = tuple(constraint.get("column_names") or ())
            if cols:
                candidates.append(cols)

        for index in inspector.get_indexes(self.TABLE_NAME):
            if index.get("unique"):
                cols = tuple(index.get("column_names") or ())
                if cols:
                    candidates.append(cols)

        preferred = []
        if has_option_symbol:
            preferred.extend(
                [
                    ("option_symbol", "quote_date"),
                    ("underlying_symbol", "option_symbol", "quote_date"),
                ]
            )
        preferred.append(
            (
                "underlying_symbol",
                "expiry",
                "quote_date",
                "strike",
                "option_type",
            )
        )

        available = set(candidates)
        return next((item for item in preferred if item in available), None)

    def _table_columns(self) -> set[str]:
        return {
            str(column["name"])
            for column in inspect(self._bind()).get_columns(self.TABLE_NAME)
        }

    def _insert_columns(self, columns: set[str]) -> tuple[str, ...]:
        return tuple(field for field in self.SUPPORTED_FIELDS if field in columns)

    def _params(
        self,
        record: OptionQuoteRecord,
        columns: set[str],
    ) -> dict[str, object]:
        return {
            key: value
            for key, value in self._all_params(record).items()
            if key in columns
        }

    def _all_params(self, record: OptionQuoteRecord) -> dict[str, object]:
        return {
            "underlying_symbol": record.identity.underlying_symbol,
            "option_symbol": self._option_symbol(record),
            "quote_date": record.quote_date,
            "expiry": record.identity.expiration_date,
            "option_type": record.identity.option_side.value,
            "strike": record.identity.strike,
            "bid": record.bid,
            "ask": record.ask,
            "last": record.last,
            "volume": record.volume,
            "open_interest": record.open_interest,
            "implied_volatility": record.implied_volatility,
            "delta": record.delta,
            "gamma": record.gamma,
            "theta": record.theta,
            "vega": record.vega,
        }

    @staticmethod
    def _option_symbol(record: OptionQuoteRecord) -> str:
        provider_symbol = str(record.provider_symbol or "").strip().upper()
        if provider_symbol:
            return provider_symbol

        identity = record.identity
        expiration = identity.expiration_date.strftime("%y%m%d")
        side = "C" if identity.option_side.value == "CALL" else "P"
        strike_code = f"{round(identity.strike * 1000):08d}"
        return (
            f"O:{identity.underlying_symbol}{expiration}{side}{strike_code}"
        )

    def _execute_many(self, statement, params) -> None:
        if isinstance(self.database, Engine):
            with self.database.begin() as connection:
                connection.execute(statement, params)
        else:
            self.database.execute(statement, params)
            self.database.commit()

    def _bind(self) -> Engine:
        if isinstance(self.database, Engine):
            return self.database
        return self.database.get_bind()

    def _dialect_name(self) -> str:
        return self._bind().dialect.name
