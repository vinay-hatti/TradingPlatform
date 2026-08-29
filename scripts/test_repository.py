from trading_ai.services.market_service import MarketService

service = MarketService()

price = service.latest_price("AAPL")

print(price)
print(price.symbol)
#if price:
#    print({
#        "symbol": price.symbol,
#        "date": str(price.date),
#        "open": price.open,
#        "high": price.high,
#        "low": price.low,
#        "close": price.close,
#        "volume": price.volume,
#    })
#else:
#    print("No data found")
