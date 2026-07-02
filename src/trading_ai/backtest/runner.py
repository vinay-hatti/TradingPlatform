class HistoricalStrategyRunner:

    def __init__(
        self,
        datasource,
        feature_pipeline,
        min_score=60,
    ):
        self.datasource = datasource
        self.feature_pipeline = feature_pipeline
        self.min_score = min_score

    def run(
        self,
        symbol,
        start_date,
        end_date,
    ):
        df = self.datasource.get_price_history(
            symbol,
            start_date,
            end_date,
        )

        if df.empty:
            return []

        features = self.feature_pipeline.run(df)

        signals = []

        for _, row in features.iterrows():

            call_score = float(row.get("call_score", 0.0) or 0.0)
            put_score = float(row.get("put_score", 0.0) or 0.0)

            if call_score <= 0 and put_score <= 0:
                continue

            if call_score >= put_score:
                signal = "CALL"
                score = call_score
            else:
                signal = "PUT"
                score = put_score

            if score < self.min_score:
                continue

            row_date = self.datasource._to_date(
                row.get("time")
            )

            signals.append({
                "date": row_date,
                "symbol": symbol,
                "signal": signal,
                "regime": row.get("market_regime", ""),
                "score": score,
                "call_score": call_score,
                "put_score": put_score,
                "close": row.get("close", 0.0),
            })

        return signals
