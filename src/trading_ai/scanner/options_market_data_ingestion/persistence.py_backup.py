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
    """
    Deterministic, schema-compatible option-history writer.

    The installed option_contract_history schema is treated as a complete
    market snapshot table. A record is persisted only when every canonical
    field required by that snapshot is present.

    This prevents repeated database failures from provider records containing
    partial quote/trade/Greek data and avoids fabricating zero values.
    """

    TABLE_NAME = "option_contract_history"

    COMPLETE_SNAPSHOT_FIELDS = (
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

    def write(
        self,
        records: Sequence[OptionQuoteRecord],
    ) -> WriteResult:
        if not records:
            return WriteResult(0, 0, 0)

        columns = self._table_columns()
        accepted, rejected = self._filter_complete_records(
            records,
            table_columns=columns,
        )

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
            inserted_records=result.inserted_records,
            updated_records=result.updated_records,
            skipped_records=result.skipped_records + rejected,
        )

    def _filter_complete_records(
        self,
        records: Sequence[OptionQuoteRecord],
        *,
        table_columns: set[str],
    ) -> tuple[tuple[OptionQuoteRecord, ...], int]:
        required_fields = tuple(
            field
            for field in self.COMPLETE_SNAPSHOT_FIELDS
            if field in table_columns
        )

        accepted: list[OptionQuoteRecord] = []
        rejected = 0

        for record in records:
            params = self._all_params(record)

            missing = [
                field
                for field in required_fields
                if self._is_missing(params.get(field))
            ]

            if missing:
                rejected += 1
                continue

            accepted.append(record)

        return tuple(accepted), rejected

    @staticmethod
    def _is_missing(value: object) -> bool:
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
        return False

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
            if column not in conflict_columns
            and column not in {"id", "created_at"}
        )

        column_sql = ",\n                ".join(insert_columns)
        value_sql = ",\n                ".join(
            f":{column}" for column in insert_columns
        )
        conflict_sql = ", ".join(conflict_columns)

        if update_columns:
            update_sql = ",\n                ".join(
                f"{column} = EXCLUDED.{column}"
                for column in update_columns
            )
            action_sql = f"DO UPDATE SET\n                {update_sql}"
        else:
            action_sql = "DO NOTHING"

        statement = text(
            f"""
            INSERT INTO {self.TABLE_NAME} (
                {column_sql}
            ) VALUES (
                {value_sql}
            )
            ON CONFLICT ({conflict_sql})
            {action_sql}
            """
        )

        params = [
            self._params(record, columns=columns)
            for record in records
        ]
        self._execute_many(statement, params)
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
            if column not in key_columns
            and column not in {"id", "created_at"}
        )

        where_sql = " AND ".join(
            f"{column} = :{column}" for column in key_columns
        )
        update_sql = ", ".join(
            f"{column} = :{column}" for column in update_columns
        )
        insert_column_sql = ", ".join(insert_columns)
        insert_value_sql = ", ".join(
            f":{column}" for column in insert_columns
        )

        select_statement = text(
            f"""
            SELECT COUNT(*)
            FROM {self.TABLE_NAME}
            WHERE {where_sql}
            """
        )
        update_statement = text(
            f"""
            UPDATE {self.TABLE_NAME}
            SET {update_sql}
            WHERE {where_sql}
            """
        )
        insert_statement = text(
            f"""
            INSERT INTO {self.TABLE_NAME} ({insert_column_sql})
            VALUES ({insert_value_sql})
            """
        )

        inserted = 0
        updated = 0

        def apply(connection) -> None:
            nonlocal inserted, updated
            for record in records:
                params = self._params(record, columns=columns)
                exists = connection.execute(
                    select_statement,
                    params,
                ).scalar_one()
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
        candidates: list[tuple[str, ...]] = []

        primary_key = inspector.get_pk_constraint(self.TABLE_NAME)
        pk_columns = tuple(primary_key.get("constrained_columns") or ())
        if pk_columns:
            candidates.append(pk_columns)

        for constraint in inspector.get_unique_constraints(self.TABLE_NAME):
            constrained = tuple(constraint.get("column_names") or ())
            if constrained:
                candidates.append(constrained)

        for index in inspector.get_indexes(self.TABLE_NAME):
            if index.get("unique"):
                constrained = tuple(index.get("column_names") or ())
                if constrained:
                    candidates.append(constrained)

        preferred: list[tuple[str, ...]] = []
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

        normalized = {tuple(candidate) for candidate in candidates}
        for candidate in preferred:
            if candidate in normalized:
                return candidate

        return None

    def _table_columns(self) -> set[str]:
        inspector = inspect(self._bind())
        return {
            str(column["name"])
            for column in inspector.get_columns(self.TABLE_NAME)
        }

    @staticmethod
    def _insert_columns(columns: set[str]) -> tuple[str, ...]:
        supported = OptionHistoryWriter.COMPLETE_SNAPSHOT_FIELDS
        return tuple(column for column in supported if column in columns)

    def _params(
        self,
        record: OptionQuoteRecord,
        *,
        columns: set[str],
    ) -> dict[str, object]:
        return {
            key: value
            for key, value in self._all_params(record).items()
            if key in columns
        }

    def _all_params(
        self,
        record: OptionQuoteRecord,
    ) -> dict[str, object]:
        return {
            "underlying_symbol": record.identity.underlying_symbol,
            "option_symbol": self._option_symbol(record),
            "expiry": record.identity.expiration_date,
            "quote_date": record.quote_date,
            "strike": record.identity.strike,
            "option_type": record.identity.option_side.value,
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
            f"O:{identity.underlying_symbol}"
            f"{expiration}{side}{strike_code}"
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
