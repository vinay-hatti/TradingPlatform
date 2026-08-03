from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
path = root / 'src/trading_ai/broker/ibkr/order_transport.py'
text = path.read_text()
assert 'def _normalize_order_compatibility' in text
assert 'order.eTradeOnly = False' in text
assert 'order.firmQuoteOnly = False' in text
assert 'o=_normalize_order_compatibility(Order())' in text
assert 'order = _normalize_order_compatibility(Order())' in text
assert 'nbboPriceCap' in text and 'unset sentinel' in text
print('IBKR order attribute compatibility assertions passed.')
