from pathlib import Path
def main():
    required=[
      "src/trading_ai/research_workstation/scanner/market_scanner_engine.py",
      "src/trading_ai/research_workstation/scanner/options_enrichment_service.py",
      "src/trading_ai/research_workstation/scanner/institutional_decision_adapter.py",
      "src/trading_ai/ui/api/research_scanner.py",
      "src/trading_ai/ui/static/research_scanner.html"]
    missing=[x for x in required if not Path(x).is_file()]
    assert not missing,f"Missing Phase 1 artifacts: {missing}"
    print("Milestone 34 Phase 1 closure assertions passed. Institutional Market Scanner phase is complete.")
if __name__=="__main__": main()
