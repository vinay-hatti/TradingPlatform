from pathlib import Path
from tempfile import TemporaryDirectory
from trading_ai.scanner.universe_management import CsvUniverseProvider, NasdaqSymbolDirectoryProvider


def main():
    with TemporaryDirectory() as directory:
        path = Path(directory) / "universe.csv"
        path.write_text(
            "symbol,name,exchange,asset_type,active,tradable,options_eligible\n"
            "AAPL,Apple,NASDAQ,EQUITY,true,true,true\n",
            encoding="utf-8",
        )
        result = CsvUniverseProvider(path).fetch()
        assert result.securities[0].symbol == "AAPL"

    nasdaq = (
        "Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
        "QQQ|Invesco QQQ|Q|N|N|100|Y|N\n"
        "File Creation Time: x\n"
    )
    other = (
        "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol\n"
        "IBM|IBM|N|IBM|N|100|N|IBM\n"
        "File Creation Time: x\n"
    )
    provider = NasdaqSymbolDirectoryProvider(
        fetch_text=lambda url: nasdaq if "nasdaqlisted" in url else other
    )
    provider_result = provider.fetch()
    assert {item.symbol for item in provider_result.securities} == {"QQQ", "IBM"}
    print("Milestone 35 Phase 1 Step 2 provider adapter assertions passed.")


if __name__ == "__main__":
    main()
