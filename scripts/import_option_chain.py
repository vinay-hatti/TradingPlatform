import argparse

from trading_ai.database.session import create_session
from trading_ai.options.importer import OptionChainCSVImporter
from trading_ai.options.repository import OptionChainRepository


def main():
    parser = argparse.ArgumentParser(
        description="Import historical option chain CSV"
    )

    parser.add_argument("--file", required=True)

    args = parser.parse_args()

    contracts = OptionChainCSVImporter().load(args.file)

    session = create_session()
    try:
        repo = OptionChainRepository(session)
        count = repo.save_many(contracts)
    finally:
        session.close()

    print()
    print("========== Option Chain Import ==========")
    print(f"File      : {args.file}")
    print(f"Contracts : {count}")
    print("=========================================")
    print()


if __name__ == "__main__":
    main()
