from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
service = (ROOT / "src/trading_ai/market_overview/service.py").read_text(encoding="utf-8")
page = (ROOT / "ui/workstation/src/pages.tsx").read_text(encoding="utf-8")

for token in (
    'CASH_INDEXES = {"SPX":"S&P 500 Index", "NDX":"Nasdaq-100 Index", "RUT":"Russell 2000 Index"}',
    'INDEX_PROXY_MAP = {"SPX":"SPY", "NDX":"QQQ", "RUT":"IWM"}',
    'breadth_universe=[s for s in universe if s not in CASH_INDEXES]',
    'volume_applicable=s not in CASH_INDEXES',
    '"asset_type":"CASH_INDEX"',
    '"strongest_cash_index":strongest_cash_index',
    '"cash_indices_as_of"',
):
    assert token in service, token

for token in (
    'Benchmark index context',
    "asset_type||'UNKNOWN'",
    'Index−ETF 20D',
    'Strongest cash index',
    'Weakest cash index',
    'Cash-index volume is intentionally excluded',
    'label="Cash indices"',
):
    assert token in page, token

assert 'for s in breadth_universe if s in valid' in service
assert 'for s in universe if s in valid and valid[s]["return_1d"]>0' not in service
print("Milestone 48 index market-overview assertions passed.")
