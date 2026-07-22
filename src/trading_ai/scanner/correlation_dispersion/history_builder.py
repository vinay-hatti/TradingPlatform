from __future__ import annotations

from collections import defaultdict
from datetime import date
from importlib import import_module
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .serialization import write_json_atomic


def resolve_database_engine() -> Engine:
    candidates = (
        ("trading_ai.database", "engine"),
        ("trading_ai.database.engine", "engine"),
        ("trading_ai.database.session", "engine"),
        ("trading_ai.database.connection", "engine"),
        ("trading_ai.database.db", "engine"),
        ("database.database", "engine"),
    )
    failures: list[str] = []

    for module_name, attribute_name in candidates:
        try:
            module = import_module(module_name)
        except ModuleNotFoundError as exc:
            failures.append(f"{module_name}: {exc}")
            continue

        candidate = getattr(module, attribute_name, None)
        if candidate is not None and hasattr(candidate, "connect"):
            return candidate

        failures.append(
            f"{module_name}: missing usable {attribute_name!r}"
        )

    raise RuntimeError(
        "Unable to locate SQLAlchemy engine. Attempts: "
        + "; ".join(failures)
    )


def build_return_history(
    *,
    symbols: list[str],
    as_of_date: date,
    lookback_rows: int,
    output_path: str | Path,
    database_engine: Engine | None = None,
) -> Path:
    engine = database_engine or resolve_database_engine()
    query = text(
        '''
        SELECT symbol, date, close
        FROM price_history
        WHERE symbol = ANY(:symbols)
          AND date <= :as_of_date
        ORDER BY symbol, date
        '''
    )

    closes: dict[str, list[float]] = defaultdict(list)
    with engine.connect() as connection:
        result = connection.execute(
            query,
            {
                "symbols": symbols,
                "as_of_date": as_of_date,
            },
        )
        for row in result.mappings():
            closes[str(row["symbol"]).strip().upper()].append(
                float(row["close"])
            )

    records: list[dict[str, Any]] = []
    for symbol in symbols:
        symbol_closes = closes.get(symbol, [])[-(lookback_rows + 1):]
        returns = [
            symbol_closes[index] / symbol_closes[index - 1] - 1.0
            for index in range(1, len(symbol_closes))
            if symbol_closes[index - 1] != 0
        ]
        records.append(
            {
                "symbol": symbol,
                "as_of_date": as_of_date.isoformat(),
                "observation_count": len(returns),
                "returns": returns,
            }
        )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")

    import json
    import os

    with temporary.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    os.replace(temporary, output)
    return output
