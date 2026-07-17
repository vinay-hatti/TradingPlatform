from __future__ import annotations
from .realtime_market_data_normalizer import RealTimeMarketDataNormalizer
from .realtime_market_data_policy import RealTimeMarketDataPolicy
from .realtime_market_data_profile import QuoteNormalizationResult, TradeNormalizationResult
from .realtime_market_data_quality_engine import RealTimeMarketDataQualityEngine

class RealTimeMarketDataService:
    def __init__(self, policy=None, normalizer=None, quality_engine=None):
        self.policy=policy or RealTimeMarketDataPolicy(); self.normalizer=normalizer or RealTimeMarketDataNormalizer(); self.quality_engine=quality_engine or RealTimeMarketDataQualityEngine(self.policy)
    def process_quote(self,event,received_at=None,previous_exchange_timestamp=None):
        q=self.normalizer.normalize_quote(event,received_at); quality=self.quality_engine.evaluate_quote(q,previous_exchange_timestamp=previous_exchange_timestamp)
        return QuoteNormalizationResult(True,quality.allowed,q,quality,quality.warnings,quality.rejection_reasons)
    def process_trade(self,event,received_at=None,previous_exchange_timestamp=None):
        t=self.normalizer.normalize_trade(event,received_at); quality=self.quality_engine.evaluate_trade(t,previous_exchange_timestamp=previous_exchange_timestamp)
        return TradeNormalizationResult(True,quality.allowed,t,quality,quality.warnings,quality.rejection_reasons)
