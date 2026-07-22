from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import MetaData, Table, delete, func, inspect, select

from trading_ai.database.session import create_session
from trading_ai.universe import CANONICAL_UNIVERSE_CSV, CanonicalUniverse

TABLE_SYMBOL_COLUMNS = {
    "price_history": "symbol",
    "option_contract_history": "underlying_symbol",
    "option_chain_history": "underlying_symbol",
    "option_history": "underlying_symbol",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete price and option rows whose symbols are not in the canonical universe CSV."
    )
    parser.add_argument("--universe-csv", default=str(CANONICAL_UNIVERSE_CSV))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    universe_path = Path(args.universe_csv)
    allowed = CanonicalUniverse(universe_path).symbols()
    if not allowed:
        raise SystemExit(f"Canonical universe is empty: {universe_path}")

    session = create_session()
    try:
        bind = session.get_bind()
        inspector = inspect(bind)
        existing = set(inspector.get_table_names())
        metadata = MetaData()
        total_removed = 0

        print("=========================================================")
        print("Canonical Universe Database Enforcement")
        print("=========================================================")
        print(f"Universe CSV                      {universe_path}")
        print(f"Allowed symbols                   {len(allowed):>10}")
        print(f"Mode                              {'DRY RUN' if args.dry_run else 'DELETE'}")

        for table_name, symbol_column in TABLE_SYMBOL_COLUMNS.items():
            if table_name not in existing:
                continue
            table = Table(table_name, metadata, autoload_with=bind)
            if symbol_column not in table.c:
                continue
            normalized = func.upper(func.trim(table.c[symbol_column]))
            condition = ~normalized.in_(allowed)
            count = int(session.execute(select(func.count()).select_from(table).where(condition)).scalar_one())
            print(f"{table_name:<32} outside={count:>10}")
            if count and not args.dry_run:
                session.execute(delete(table).where(condition))
                total_removed += count

        if args.dry_run:
            session.rollback()
        else:
            session.commit()
        print(f"Rows removed                      {total_removed:>10}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
