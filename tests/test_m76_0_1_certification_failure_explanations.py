from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def txt(name): return (ROOT/'ui/workstation/src'/name).read_text()

def test_stock_scanner_pairs_code_and_persisted_reason():
    s=txt('StockIntelligenceScannerPage.tsx')
    assert 'certificationFailureReasons:string[] = certification.failure_reasons || []' in s
    assert '<b>{code}:</b> {certificationFailureReasons[index]' in s

def test_trade_builder_pairs_code_and_persisted_reason():
    s=txt('AdvancedTradeBuilderPage.tsx')
    assert '<b>Certification failures</b>' in s
    assert "(c.failure_reasons||[])[index]" in s

def test_execution_workspace_pairs_code_and_persisted_reason():
    s=txt('ExecutionWorkspacePage.tsx')
    assert '<b>Certification failures</b>' in s
    assert "(c.failure_reasons||[])[index]" in s

def test_institutional_options_retains_code_reason_contract():
    s=txt('InstitutionalOptionsPage.tsx')
    assert "{x}: {finalCert.failure_reasons?.[i]" in s
