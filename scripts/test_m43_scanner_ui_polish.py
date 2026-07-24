from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    pages = (root / "ui/workstation/src/pages.tsx").read_text(encoding="utf-8")
    styles = (root / "ui/workstation/src/styles.css").read_text(encoding="utf-8")
    components = (root / "ui/workstation/src/components.tsx").read_text(encoding="utf-8")
    ingestion = (root / "scripts/run_market_ingestion.py").read_text(encoding="utf-8")

    assert "r.contract_ticker||r.option_symbol||r.contract_symbol||'—'" in pages
    assert "label:'Ingestion mode'" in pages
    assert "Refresh missing / stale" in pages
    assert 'title="Data architecture" compact' in pages
    assert 'title="Provider health and lineage" compact' in pages
    assert 'title="Run history" compact' in pages
    assert ".run-history-scroll{height:255px" in styles
    assert ".compact-card" in styles
    assert "compact?:boolean" in components
    assert 'default=4,help="Concurrent Yahoo OHLCV workers' in ingestion
    assert 'default=1.0,help="Global minimum seconds between Yahoo requests' in ingestion
    print("Milestone 43 scanner UI polish and ingestion performance assertions passed.")


if __name__ == "__main__":
    main()
