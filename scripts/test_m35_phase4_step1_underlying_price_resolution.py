from unittest.mock import Mock

from trading_ai.scanner.historical_options_feature_store.service import (
    HistoricalOptionFeatureService,
)


class FakeInspector:
    def __init__(self, tables):
        self.tables = tables

    def get_columns(self, table_name):
        return [
            {"name": name}
            for name in self.tables.get(table_name, ())
        ]


def main():
    option_columns = (
        "id",
        "underlying_symbol",
        "option_symbol",
        "quote_date",
        "expiry",
        "option_type",
        "strike",
        "bid",
        "ask",
        "mid",
        "last",
        "volume",
        "open_interest",
        "implied_volatility",
        "delta",
        "gamma",
        "theta",
        "vega",
        "rho",
    )
    price_columns = (
        "symbol",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
    )

    inspector = FakeInspector(
        {
            "option_contract_history": option_columns,
            "price_history": price_columns,
        }
    )

    service = HistoricalOptionFeatureService.__new__(
        HistoricalOptionFeatureService
    )
    service.session = Mock()
    service._underlying_price_source = "unresolved"

    import trading_ai.scanner.historical_options_feature_store.service as module

    original = module.inspect
    module.inspect = lambda bind: inspector
    try:
        statement = service._build_source_statement()
    finally:
        module.inspect = original

    sql = str(statement)
    assert 'LEFT JOIN "price_history" ph' in sql
    assert 'ph."close" AS underlying_price' in sql
    assert 'ph."symbol"' in sql
    assert 'ph."date" = oc.quote_date' in sql
    assert (
        service._underlying_price_source
        == "price_history.close"
    )

    print(
        "Milestone 35 Phase 4 Step 1 underlying-price "
        "resolution assertions passed."
    )


if __name__ == "__main__":
    main()
