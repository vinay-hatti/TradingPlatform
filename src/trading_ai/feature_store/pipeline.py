from trading_ai.feature_store.regime import RegimeEngine
from trading_ai.utils.safe_access import ensure_columns
from trading_ai.domain.context import TradeContext
from trading_ai.feature_store.schema import validate_market_df
import numpy as np
import pandas as pd


class FeaturePipeline:

    def __init__(self, engine, scorer):
        self.engine = engine
        self.scorer = scorer
        self.regime_engine = RegimeEngine()

    def run(self, df):

        # ----------------------------
        # Validate schema
        # ----------------------------
        df = validate_market_df(df)

        df = ensure_columns(df, [
            "ema20", "ema50", "ema200",
            "rsi14",
            "atr14",
            "market_regime",
            "close",
        ])

        # ----------------------------
        # Features
        # ----------------------------
        df = self.engine.build_features(df)

        # ----------------------------
        # Regime
        # ----------------------------
        df = self.regime_engine.compute(df)

        # ----------------------------
        # SAFE ATR derived features (🔥 FIX)
        # ----------------------------
        df["atr14"] = df.get("atr14", 0.0)

        # FIX: missing mean used by scorer
        df["atr14_mean"] = (
            df["atr14"].rolling(20, min_periods=1).mean()
        )

        # ----------------------------
        # IV synthetic fallback
        # ----------------------------
        df["iv"] = df.get("iv", df["atr14"] / df["close"])
        df["iv"] = df["iv"].replace([np.inf, -np.inf], np.nan).fillna(0.0)

        # ----------------------------
        # Expected move
        # ----------------------------
        trading_days = 365
        t = 1 / trading_days

        df["expected_move_1d"] = df["close"] * df["iv"] * np.sqrt(t)
        df["em_ratio"] = df["expected_move_1d"] / df["close"]

        # ----------------------------
        # Scoring (now safe)
        # ----------------------------
        df["call_score"] = df.apply(self.scorer.score_long_call, axis=1)
        df["put_score"] = df.apply(self.scorer.score_long_put, axis=1)

        # ----------------------------
        # IV rank
        # ----------------------------
        latest = df.iloc[-1]
        iv_rank = float(np.clip(latest.get("iv", 0.5), 0.0, 1.0))
        df["iv_rank"] = iv_rank

        # ----------------------------
        # Trade context (CRITICAL)
        # ----------------------------
        df["trade_context"] = df.apply(
            lambda row: TradeContext(
                symbol=str(row.get("symbol", "UNKNOWN")),
                close=float(row.get("close", 0.0)),
                ema20=float(row.get("ema20", 0.0)),
                ema50=float(row.get("ema50", 0.0)),
                ema200=float(row.get("ema200", 0.0)),
                rsi14=float(row.get("rsi14", 0.0)),
                atr14=float(row.get("atr14", 0.0)),
                market_regime=str(row.get("market_regime", "CHOP")),
                call_score=float(row.get("call_score", 0.0)),
                put_score=float(row.get("put_score", 0.0)),
                expected_move_1d=float(row.get("expected_move_1d", 0.0)),
                em_ratio=float(row.get("em_ratio", 0.0)),
                iv=float(row.get("iv", 0.0)),   # ✅ FIX: REQUIRED FIELD
                iv_rank=float(row.get("iv_rank", 0.5)),
                option=None,
            ),
            axis=1,
        )

        # ----------------------------
        # Debug safety
        # ----------------------------
        if float(latest["em_ratio"]) > 0.15:
            print("WARNING: Expected move exceeds 15%")

        return df
