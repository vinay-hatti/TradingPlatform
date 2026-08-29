from pathlib import Path
root=Path(__file__).resolve().parents[1]
checks={
 'stock_reason_alignment': ('ui/workstation/src/StockIntelligenceScannerPage.tsx','certificationFailureReasons[index]'),
 'stock_rule_sentence': ('ui/workstation/src/StockIntelligenceScannerPage.tsx','<b>{code}:</b>'),
 'trade_builder_reason_alignment': ('ui/workstation/src/AdvancedTradeBuilderPage.tsx',"(c.failure_reasons||[])[index]"),
 'trade_builder_rule_sentence': ('ui/workstation/src/AdvancedTradeBuilderPage.tsx','<b>{code}:</b>'),
 'execution_reason_alignment': ('ui/workstation/src/ExecutionWorkspacePage.tsx',"(c.failure_reasons||[])[index]"),
 'execution_rule_sentence': ('ui/workstation/src/ExecutionWorkspacePage.tsx','<b>{code}:</b>'),
 'institutional_options_reason_alignment': ('ui/workstation/src/InstitutionalOptionsPage.tsx','finalCert.failure_reasons?.[i]'),
 'legacy_fallback': ('ui/workstation/src/StockIntelligenceScannerPage.tsx','Certification rule failed.'),
}
for name,(rel,needle) in checks.items():
    text=(root/rel).read_text()
    assert needle in text, f'{name}: missing {needle}'
    print('PASS',name)
print('M76.0.1 certification failure explanations verification: PASSED')
