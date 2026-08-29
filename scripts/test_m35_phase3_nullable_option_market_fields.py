from sqlalchemy import inspect
from trading_ai.database import engine

IDENTITY = (
    "underlying_symbol",
    "option_symbol",
    "quote_date",
    "expiry",
    "option_type",
    "strike",
)

MARKET = (
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

def main() -> None:
    columns = {
        column["name"]: column
        for column in inspect(engine).get_columns("option_contract_history")
    }

    errors = []

    for name in IDENTITY:
        if name not in columns:
            errors.append(f"missing identity column: {name}")
        elif columns[name]["nullable"]:
            errors.append(f"identity column unexpectedly nullable: {name}")

    for name in MARKET:
        if name not in columns:
            errors.append(f"missing market column: {name}")
        elif not columns[name]["nullable"]:
            errors.append(f"market column still NOT NULL: {name}")

    if errors:
        raise AssertionError("\n".join(errors))

    print(
        "Milestone 35 Phase 3 nullable option market-field assertions passed."
    )

if __name__ == "__main__":
    main()
