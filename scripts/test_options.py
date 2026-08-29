from polygon import RESTClient
from trading_ai.config import settings

client = RESTClient(settings.polygon_api_key)

total = 0
quotes = 0
greeks = 0
ivs = 0

for c in client.list_snapshot_options_chain("AAPL"):
    total += 1

    if c.last_quote:
        quotes += 1

    if c.greeks and c.greeks.delta is not None:
        greeks += 1

    if c.implied_volatility is not None:
        ivs += 1

print(f"Total contracts : {total}")
print(f"With quotes     : {quotes}")
print(f"With greeks     : {greeks}")
print(f"With IV         : {ivs}")
