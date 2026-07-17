from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from trading_ai.strategy_engine.adaptive_strategy_profile import StrategyPerformanceProfile
from trading_ai.strategy_engine.strategy_learning_dataset import StrategyLearningDatasetBuilder
from trading_ai.strategy_engine.strategy_learning_engine import StrategyLearningEngine
from trading_ai.strategy_engine.strategy_learning_policy import StrategyLearningPolicy
from trading_ai.strategy_engine.strategy_learning_profile import StrategyLearningProfile, StrategyWeightingProfile


class StrategyLearningService:
    """Application service for dataset construction, learning, and dynamic weighting."""

    def __init__(self, policy: StrategyLearningPolicy | None = None):
        self.policy = policy or StrategyLearningPolicy()
        self.dataset_builder = StrategyLearningDatasetBuilder(self.policy)
        self.engine = StrategyLearningEngine(self.policy)

    def learn(self, outcomes: Iterable[Any], as_of_date: date | None = None) -> dict[str, StrategyLearningProfile]:
        records = self.dataset_builder.build(outcomes, as_of_date=as_of_date)
        return self.engine.learn(records, as_of_date=as_of_date)

    def build_dynamic_weights(
        self,
        profiles: dict[str, StrategyLearningProfile] | Iterable[StrategyLearningProfile],
        prior_weights: dict[str, float] | None = None,
    ) -> StrategyWeightingProfile:
        values = profiles.values() if isinstance(profiles, dict) else profiles
        return self.engine.dynamic_weights(values, prior_weights=prior_weights)

    @staticmethod
    def to_adaptive_performance_profiles(profiles: dict[str, StrategyLearningProfile]) -> dict[str, StrategyPerformanceProfile]:
        converted: dict[str, StrategyPerformanceProfile] = {}
        for strategy, profile in profiles.items():
            best_context = max((segment for segment in profile.segments if segment.valid), key=lambda item: item.observation_count, default=None)
            converted[strategy] = StrategyPerformanceProfile(
                strategy=strategy,
                observation_count=profile.observation_count,
                win_rate=profile.weighted_win_rate,
                average_return=profile.weighted_average_return,
                profit_factor=profile.profit_factor,
                maximum_drawdown_pct=profile.maximum_drawdown_pct,
                sharpe_ratio=profile.sharpe_ratio,
                calibration_score=profile.calibration_score,
                execution_score=profile.execution_score,
                context_observation_count=best_context.observation_count if best_context else 0,
                context_win_rate=best_context.weighted_win_rate if best_context else None,
                context_average_return=best_context.weighted_average_return if best_context else None,
                metadata={"learning_profile": profile, "source": "StrategyLearningService"},
            )
        return converted
