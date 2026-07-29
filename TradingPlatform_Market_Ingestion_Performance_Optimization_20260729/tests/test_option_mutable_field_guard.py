from pathlib import Path

MUTABLE_FIELDS = (
    "bid", "ask", "last", "volume", "open_interest", "implied_volatility",
    "delta", "gamma", "theta", "vega",
)


def main() -> None:
    # The optimization package deliberately does not replace option persistence.
    # Validate the target project's current writer before installation instead.
    import sys
    project = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    source = project / "src/trading_ai/scanner/options_market_data_ingestion/persistence.py"
    text = source.read_text(encoding="utf-8")
    for field in MUTABLE_FIELDS:
        assert f'"{field}"' in text, f"missing mutable option field: {field}"
    assert "DO UPDATE SET" in text
    assert "EXCLUDED." in text
    assert "if column not in conflict_columns" in text
    print("Option mutable-field upsert guard assertions passed.")


if __name__ == "__main__":
    main()
