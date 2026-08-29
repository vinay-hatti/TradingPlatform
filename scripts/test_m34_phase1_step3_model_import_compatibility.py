from trading_ai.database.models import OptionContractHistory
from trading_ai.research_workstation.scanner.options_data_adapter import (
    OptionContractSnapshot,
    OptionHistoryDataAdapter,
)


def main() -> None:
    assert OptionContractHistory is not None
    assert OptionContractSnapshot is not None
    assert OptionHistoryDataAdapter is not None
    assert hasattr(OptionHistoryDataAdapter, "load_contracts")

    print("Milestone 34 Phase 1 Step 3 option-model import compatibility passed.")


if __name__ == "__main__":
    main()
