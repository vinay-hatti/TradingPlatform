from trading_ai.market.service import MarketService
from trading_ai.market.transformer import bars_to_dataframe

service = MarketService()

bars = service.get_history("AAPL", "2026-01-01", "2026-06-01")

for b in bars[:3]:
    print(b)

#df = service.provider.to_dataframe(bars)
df = bars_to_dataframe(bars)

print(df.tail())
