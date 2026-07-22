from datetime import date
from types import SimpleNamespace

from trading_ai.scanner.options_market_data_ingestion.persistence import (
    OptionHistoryWriter,
)
from trading_ai.scanner.options_market_data_quality.contracts import (
    OptionContractIdentity,
    OptionQuoteRecord,
    OptionSide,
)


def make_record(*, bid, ask):
    return OptionQuoteRecord(
        identity=OptionContractIdentity(
            underlying_symbol="A",
            expiration_date=date(2026, 8, 21),
            strike=120.0,
            option_side=OptionSide.PUT,
        ),
        quote_date=date(2026, 7, 20),
        bid=bid,
        ask=ask,
        last=1.5,
        volume=133,
        open_interest=109,
        implied_volatility=0.349,
        delta=-0.19,
        gamma=0.02,
        theta=-0.05,
        vega=0.09,
        provider_symbol="O:A260821P00120000",
    )


def main():
    writer = object.__new__(OptionHistoryWriter)

    metadata = {
        "id": {
            "nullable": False,
            "default": None,
            "identity": None,
            "computed": None,
            "autoincrement": True,
        },
        "bid": {
            "nullable": False,
            "default": None,
            "identity": None,
            "computed": None,
            "autoincrement": "auto",
        },
        "ask": {
            "nullable": False,
            "default": None,
            "identity": None,
            "computed": None,
            "autoincrement": "auto",
        },
        "last": {
            "nullable": False,
            "default": None,
            "identity": None,
            "computed": None,
            "autoincrement": "auto",
        },
    }

    accepted, rejected = writer._filter_schema_compatible_records(
        [make_record(bid=None, ask=None), make_record(bid=1.4, ask=1.6)],
        column_metadata=metadata,
    )

    assert len(accepted) == 1
    assert rejected == 1
    assert accepted[0].bid == 1.4

    print(
        "Milestone 35 Phase 3 PostgreSQL metadata null-filter assertions passed."
    )


if __name__ == "__main__":
    main()
