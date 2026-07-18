from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    app = (
        root / "src/trading_ai/ui/static/app.js"
    ).read_text(encoding="utf-8")

    assert 'selectedSymbol = new URLSearchParams' in app
    assert '/api/v1/symbols/${encodeURIComponent(symbol)}' in app
    assert '/api/v1/symbols?symbol=${encodeURIComponent(symbol)}' in app
    assert '/api/v1/symbol-intelligence/${encodeURIComponent(symbol)}' in app
    assert "async function fetchSymbolPayload" in app
    assert 'id="symbolSearch"' in app
    assert 'id="symbolInput"' in app
    assert 'currentView === "symbols"' in app
    assert "No compatible Symbol Intelligence API route responded" in app

    print(
        "All corrected Milestone 31 Phase 10 Symbol Intelligence "
        "route assertions passed."
    )


if __name__ == "__main__":
    main()
