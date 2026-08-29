from trading_ai.market.universe import FULL_UNIVERSE_LIMIT, get_universe, list_universes


def main() -> None:
    universes = {item["id"]: item for item in list_universes()}
    expected = {"liquid-us-700", "sp500-top100", "sp500", "nasdaq100", "major-etfs"}
    assert expected.issubset(universes), universes.keys()
    full = get_universe("liquid-us-700")
    assert 1 <= len(full) <= FULL_UNIVERSE_LIMIT
    assert len(full) == len(set(full))
    assert len(get_universe("sp500-top100")) == 100
    assert all(item["symbol_count"] == len(get_universe(item["id"])) for item in universes.values())
    print("Milestone 43 universe registry assertions passed.")


if __name__ == "__main__":
    main()
