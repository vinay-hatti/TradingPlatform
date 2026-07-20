from trading_ai.database import SessionLocal
from trading_ai.database.repositories.option_chain import OptionChainRepository


def main() -> None:
    with SessionLocal() as session:
        repository = OptionChainRepository(session)
        repository.get_range(("AAPL",))
        if repository.resolved_table_name is None:
            print("No compatible option-chain table was found.")
            print("Required logical fields:")
            for name, aliases in repository.REQUIRED_COLUMN_GROUPS.items():
                print(f"  {name}: {', '.join(aliases)}")
            return
        print(f"Compatible option-chain table: {repository.resolved_table_name}")
        print("Resolved columns:")
        for logical, actual in sorted(repository._column_map.items()):
            print(f"  {logical:<20} -> {actual}")


if __name__ == "__main__":
    main()
