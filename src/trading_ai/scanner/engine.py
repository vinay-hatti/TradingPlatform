from trading_ai.market.transformer import bars_to_dataframe


class ScannerEngine:

    def __init__(self, market, pipeline, signal_engine, strategy_engine):
        self.market = market
        self.pipeline = pipeline
        self.signal_engine = signal_engine
        self.strategy_engine = strategy_engine

    def scan(self, symbols, start, end):

        all_dfs = []

        # ----------------------------
        # STEP 1: FETCH ALL DATA FIRST
        # ----------------------------
        for symbol in symbols:
            bars = self.market.get_history(symbol, start, end)
            df = bars_to_dataframe(bars)
            all_dfs.append(df)
        analytics = self.market.provider.analytics

        for symbol in symbols:

            df = self.market.get_history(symbol, start, end)
            df = self.pipeline.run(df)

            ctx = df.iloc[-1]["trade_context"]

            trade = self.strategy_engine.recommend(
                symbol,
                ctx,
                analytics
            )

            if trade:
                print(trade)
                results.append(trade)

        return results
