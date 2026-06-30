from trading_ai.market.service import MarketService
from trading_ai.indicators.feature_engine import FeatureEngine
from trading_ai.options.scoring import OptionsScoringEngine

from trading_ai.feature_store.pipeline import FeaturePipeline
from trading_ai.scanner.engine import ScannerEngine
from trading_ai.scanner.signals_engine import SignalEngine
from trading_ai.strategy.engine import StrategyEngine

from trading_ai.options.engine import OptionsEngine
from trading_ai.options.providers.simulated import SimulatedOptionsProvider
from trading_ai.options.providers.polygon_iv import PolygonIVProvider
from trading_ai.options.providers.polygon import PolygonOptionsProvider

class Container:

    def __init__(self):

        # -------------------------
        # Market layer
        # -------------------------
        self.market = MarketService()

        # -------------------------
        # Feature / signals
        # -------------------------
        self.feature_engine = FeatureEngine()
        self.signal_engine = SignalEngine()

        self.scorer = OptionsScoringEngine()
        self.pipeline = FeaturePipeline(
            self.feature_engine,
            self.scorer
        )

        self.iv_provider = PolygonIVProvider()

        # -------------------------
        # Options provider (PRIMARY FIX AREA)
        # -------------------------
        self.options_provider = PolygonOptionsProvider()
        self.market.provider.options_provider = self.options_provider

        # IMPORTANT: inject into market provider (fix missing analytics chain)
        if hasattr(self.market, "provider"):
            self.market.provider.options_provider = self.options_provider

        # -------------------------
        # Options engine
        # -------------------------
        self.options_engine = OptionsEngine(
            provider=self.options_provider
        )

        # IMPORTANT: keep scoring aligned with IV provider
        self.scorer = OptionsScoringEngine(
            iv_provider=self.iv_provider
        )

        # -------------------------
        # Strategy layer
        # -------------------------
        self.strategy_engine = StrategyEngine(
            options_engine=self.options_engine
        )

        # -------------------------
        # Scanner
        # -------------------------
        self.scanner = ScannerEngine(
            market=self.market,
            pipeline=self.pipeline,
            signal_engine=self.signal_engine,
            strategy_engine=self.strategy_engine,
        )
