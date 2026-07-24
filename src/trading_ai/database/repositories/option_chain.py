from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from sqlalchemy import MetaData, Table, func, inspect, select

from trading_ai.database.repositories.base import BaseRepository


class OptionChainRepository(BaseRepository):
    """Repository-native reader for historical option-chain records.

    The current project has no option-chain ORM model. This repository therefore
    discovers a compatible SQL table by its columns and reads it through SQLAlchemy
    Core. No model import or parallel ORM hierarchy is required.
    """

    REQUIRED_COLUMN_GROUPS = {
        "symbol": ("underlying_symbol", "symbol", "underlying"),
        "quote_date": ("quote_date", "date", "as_of_date"),
        "expiry": ("expiry", "expiration", "expiration_date"),
        "strike": ("strike",),
        "option_type": ("option_type", "type", "right"),
        "bid": ("bid",),
        "ask": ("ask",),
        "volume": ("volume",),
        "open_interest": ("open_interest", "openinterest", "oi"),
        "implied_volatility": ("implied_volatility", "iv"),
    }

    OPTIONAL_COLUMN_GROUPS = {
        "contract_ticker": (
            "option_symbol",
            "contract_ticker",
            "ticker",
            "option_ticker",
            "contract_symbol",
        ),
        "last": ("last", "last_price", "mark"),
        "delta": ("delta",),
        "gamma": ("gamma",),
        "theta": ("theta",),
        "vega": ("vega",),
    }

    PREFERRED_TABLE_NAMES = (
        "option_contract_history",
        "option_chain_history",
        "option_history",
        "option_chain",
        "options_history",
    )

    def __init__(self, session, table_name: str | None = None):
        super().__init__(session)
        self.requested_table_name = table_name
        self._resolved_table_name: str | None = None
        self._column_map: dict[str, str] = {}

    @staticmethod
    def _resolve_alias(columns: set[str], aliases: tuple[str, ...]) -> str | None:
        lowered = {column.lower(): column for column in columns}
        for alias in aliases:
            if alias.lower() in lowered:
                return lowered[alias.lower()]
        return None

    def _candidate_tables(self) -> list[str]:
        inspector = inspect(self.session.get_bind())
        names = inspector.get_table_names()
        if self.requested_table_name:
            return [self.requested_table_name] if self.requested_table_name in names else []
        preferred = [name for name in self.PREFERRED_TABLE_NAMES if name in names]
        remaining = [name for name in names if name not in preferred]
        return preferred + remaining

    def _resolve_table(self) -> tuple[Table, dict[str, str]] | None:
        if self._resolved_table_name:
            metadata = MetaData()
            table = Table(
                self._resolved_table_name,
                metadata,
                autoload_with=self.session.get_bind(),
            )
            return table, dict(self._column_map)

        inspector = inspect(self.session.get_bind())
        for table_name in self._candidate_tables():
            columns = {item["name"] for item in inspector.get_columns(table_name)}
            mapping: dict[str, str] = {}
            compatible = True
            for canonical, aliases in self.REQUIRED_COLUMN_GROUPS.items():
                resolved = self._resolve_alias(columns, aliases)
                if resolved is None:
                    compatible = False
                    break
                mapping[canonical] = resolved
            if not compatible:
                continue
            for canonical, aliases in self.OPTIONAL_COLUMN_GROUPS.items():
                resolved = self._resolve_alias(columns, aliases)
                if resolved is not None:
                    mapping[canonical] = resolved

            metadata = MetaData()
            table = Table(table_name, metadata, autoload_with=self.session.get_bind())
            self._resolved_table_name = table_name
            self._column_map = mapping
            return table, mapping
        return None

    @property
    def resolved_table_name(self) -> str | None:
        return self._resolved_table_name

    def get_latest_snapshot(
        self,
        symbol: str,
        as_of: date,
    ) -> list[dict[str, Any]]:
        """Return the newest available snapshot on or before ``as_of``.

        Option ingestion commonly completes after the market close while a scan
        can run on the following calendar day. An exact-date lookup therefore
        incorrectly reports no data even though the prior trading-day snapshot
        is valid and is the latest persisted information available.
        """
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            return []

        resolved = self._resolve_table()
        if resolved is None:
            return []
        table, mapping = resolved

        quote_date_column = table.c[mapping["quote_date"]]
        symbol_column = table.c[mapping["symbol"]]

        latest_quote_date = self.session.execute(
            select(func.max(quote_date_column)).where(
                symbol_column == normalized_symbol,
                quote_date_column <= as_of,
            )
        ).scalar_one_or_none()
        if latest_quote_date is None:
            return []

        selected_columns = [
            table.c[actual].label(canonical)
            for canonical, actual in mapping.items()
        ]
        statement = (
            select(*selected_columns)
            .where(
                symbol_column == normalized_symbol,
                quote_date_column == latest_quote_date,
            )
            .order_by(
                table.c[mapping["expiry"]],
                table.c[mapping["strike"]],
            )
        )
        return [dict(row._mapping) for row in self.session.execute(statement)]

    def get_range(
        self,
        symbols: Iterable[str],
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, Any]]:
        normalized = tuple(
            dict.fromkeys(
                symbol.strip().upper()
                for symbol in symbols
                if symbol and symbol.strip()
            )
        )
        if not normalized:
            return []

        resolved = self._resolve_table()
        if resolved is None:
            return []
        table, mapping = resolved

        selected_columns = [
            table.c[actual].label(canonical)
            for canonical, actual in mapping.items()
        ]
        statement = select(*selected_columns).where(
            table.c[mapping["symbol"]].in_(normalized)
        )
        if start is not None:
            statement = statement.where(table.c[mapping["quote_date"]] >= start)
        if end is not None:
            statement = statement.where(table.c[mapping["quote_date"]] <= end)
        statement = statement.order_by(
            table.c[mapping["symbol"]],
            table.c[mapping["quote_date"]],
            table.c[mapping["expiry"]],
            table.c[mapping["strike"]],
        )
        return [dict(row._mapping) for row in self.session.execute(statement)]
