from pathlib import Path
root=Path(__file__).resolve().parents[1]
src=(root/'ui/workstation/src/PortfolioIntelligenceRefinedPage.tsx').read_text()
css=(root/'ui/workstation/src/portfolio-intelligence-refined.css').read_text()
required=[
 'AUTO MANAGED','MANUAL MANAGEMENT REQUIRED','AUTO MANAGEMENT DEGRADED',
 'You must manually manage this position through closure',
 "automationMode === 'FULLY_AUTOMATIC'",'activeExitCount > 0','canonicalLineage',
 'dynamicPositionManagementApi.instructions()','managementFilter','Auto managed','Manual required','Automation degraded'
]
for marker in required:
    assert marker in src, marker
for marker in ['.pi-management-badge.auto','.pi-management-badge.manual','.pi-management-badge.degraded','.pi-management-banner.manual']:
    assert marker in css, marker
print('M74.9 autonomous-management visibility verification: PASSED')
