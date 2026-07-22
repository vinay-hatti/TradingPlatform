from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from .contracts import (
    SectorLeadershipGovernanceStatus,
    SectorLeadershipProfile,
    SectorRankProfile,
)
from .policy import SectorLeadershipPolicy


OFFENSIVE_SECTORS = frozenset({"XLK", "XLY", "XLI", "XLF", "XLC"})
DEFENSIVE_SECTORS = frozenset({"XLP", "XLU", "XLV", "XLRE"})
CYCLICAL_SECTORS = frozenset({"XLE", "XLB"})


class SectorLeadershipEngine:
    def __init__(
        self,
        policy: SectorLeadershipPolicy | None = None,
    ) -> None:
        self.policy = policy or SectorLeadershipPolicy()

    def evaluate(
        self,
        *,
        as_of_date: date,
        features_by_symbol: Mapping[str, Mapping[str, Any]],
    ) -> SectorLeadershipProfile:
        sector_records = {
            symbol: record
            for symbol, record in features_by_symbol.items()
            if record.get("asset_class") == "SECTOR"
        }

        governed = {
            symbol: record
            for symbol, record in sector_records.items()
            if record.get("governance_status") in {"READY", "REVIEW"}
        }

        status, reasons = self._govern(len(governed))

        scored: list[tuple[str, Mapping[str, Any], float]] = []
        for symbol, record in governed.items():
            score = self._momentum_score(record)
            scored.append((symbol, record, score))

        scored.sort(key=lambda item: (-item[2], item[0]))

        rankings: list[SectorRankProfile] = []
        count = len(scored)

        for index, (symbol, record, score) in enumerate(scored, start=1):
            percentile = (
                1.0
                if count <= 1
                else 1.0 - ((index - 1) / (count - 1))
            )
            rankings.append(
                SectorRankProfile(
                    symbol=symbol,
                    group=str(record.get("group", "")),
                    classification=self._classification(symbol),
                    return_5d=self._float(record.get("return_5d")),
                    return_21d=self._float(record.get("return_21d")),
                    relative_strength_21d=self._float(
                        record.get("relative_strength_21d")
                    ),
                    trend_direction=str(
                        record.get("trend_direction", "NOT_OBSERVED")
                    ),
                    trend_strength=self._float(
                        record.get("trend_strength")
                    ),
                    liquidity_regime=str(
                        record.get("liquidity_regime", "NOT_OBSERVED")
                    ),
                    momentum_score=score,
                    rank=index,
                    percentile=percentile,
                    is_leader=index <= self.policy.leader_count,
                    is_laggard=index > max(
                        0,
                        count - self.policy.laggard_count,
                    ),
                )
            )

        advancing = sum(
            (rank.return_21d or 0.0) > 0.0
            for rank in rankings
            if rank.return_21d is not None
        )
        declining = sum(
            (rank.return_21d or 0.0) < 0.0
            for rank in rankings
            if rank.return_21d is not None
        )
        positive_rs = sum(
            (rank.relative_strength_21d or 0.0) > 0.0
            for rank in rankings
            if rank.relative_strength_21d is not None
        )
        uptrend = sum(
            rank.trend_direction == "UP"
            for rank in rankings
        )

        breadth_score = (
            (
                advancing
                + positive_rs
                + uptrend
            )
            / (3.0 * count)
            if count
            else 0.0
        )

        offensive_score = self._classification_score(
            rankings,
            "OFFENSIVE",
        )
        defensive_score = self._classification_score(
            rankings,
            "DEFENSIVE",
        )
        leadership_spread = offensive_score - defensive_score

        leadership_state = self._leadership_state(leadership_spread)
        rotation_state = self._rotation_state(
            breadth_score=breadth_score,
            leadership_spread=leadership_spread,
        )

        completeness = min(
            1.0,
            count / self.policy.minimum_sectors_ready,
        )
        conviction = min(
            1.0,
            abs(leadership_spread) + abs(breadth_score - 0.5),
        )
        confidence = completeness * conviction

        leaders = tuple(
            rank.symbol
            for rank in rankings
            if rank.is_leader
        )
        laggards = tuple(
            rank.symbol
            for rank in rankings
            if rank.is_laggard
        )

        return SectorLeadershipProfile(
            as_of_date=as_of_date,
            benchmark_symbol=self.policy.benchmark_symbol,
            sector_count=len(sector_records),
            governed_sector_count=count,
            advancing_sector_count=advancing,
            declining_sector_count=declining,
            positive_relative_strength_count=positive_rs,
            uptrend_sector_count=uptrend,
            breadth_score=breadth_score,
            offensive_leadership_score=offensive_score,
            defensive_leadership_score=defensive_score,
            leadership_spread=leadership_spread,
            rotation_state=rotation_state,
            leadership_state=leadership_state,
            confidence=confidence,
            leaders=leaders,
            laggards=laggards,
            rankings=tuple(rankings),
            governance_status=status,
            governance_reasons=tuple(reasons),
        )

    def _momentum_score(
        self,
        record: Mapping[str, Any],
    ) -> float:
        return_5d = self._float(record.get("return_5d")) or 0.0
        relative_strength = (
            self._float(record.get("relative_strength_21d")) or 0.0
        )
        trend_direction = str(
            record.get("trend_direction", "NOT_OBSERVED")
        )
        trend_strength = self._float(record.get("trend_strength")) or 0.0

        trend_direction_value = {
            "UP": 1.0,
            "MIXED": 0.0,
            "DOWN": -1.0,
            "NOT_OBSERVED": 0.0,
        }.get(trend_direction, 0.0)

        return (
            self.policy.return_5d_weight * return_5d
            + self.policy.relative_strength_21d_weight
            * relative_strength
            + self.policy.trend_direction_weight
            * trend_direction_value
            + self.policy.trend_strength_weight
            * min(1.0, max(0.0, trend_strength))
        )

    def _classification_score(
        self,
        rankings: list[SectorRankProfile],
        classification: str,
    ) -> float:
        values = [
            rank.momentum_score
            for rank in rankings
            if rank.classification == classification
        ]
        return sum(values) / len(values) if values else 0.0

    def _leadership_state(
        self,
        leadership_spread: float,
    ) -> str:
        if (
            leadership_spread
            >= self.policy.risk_on_leadership_threshold
        ):
            return "OFFENSIVE"
        if (
            leadership_spread
            <= self.policy.risk_off_leadership_threshold
        ):
            return "DEFENSIVE"
        return "BALANCED"

    def _rotation_state(
        self,
        *,
        breadth_score: float,
        leadership_spread: float,
    ) -> str:
        if (
            breadth_score >= self.policy.broad_participation_threshold
            and leadership_spread
            >= self.policy.risk_on_leadership_threshold
        ):
            return "BROAD_RISK_ON"

        if (
            breadth_score <= self.policy.narrow_participation_threshold
            and leadership_spread
            <= self.policy.risk_off_leadership_threshold
        ):
            return "DEFENSIVE_ROTATION"

        if (
            breadth_score < self.policy.broad_participation_threshold
            and leadership_spread
            >= self.policy.risk_on_leadership_threshold
        ):
            return "NARROW_RISK_ON"

        if (
            breadth_score >= self.policy.broad_participation_threshold
            and leadership_spread
            <= self.policy.risk_off_leadership_threshold
        ):
            return "DEFENSIVE_BREADTH"

        return "MIXED_ROTATION"

    def _govern(
        self,
        governed_sector_count: int,
    ) -> tuple[SectorLeadershipGovernanceStatus, list[str]]:
        if governed_sector_count < self.policy.minimum_sectors_review:
            return (
                SectorLeadershipGovernanceStatus.EXCLUDED,
                [
                    f"governed sector count {governed_sector_count} < "
                    f"{self.policy.minimum_sectors_review}"
                ],
            )

        if governed_sector_count < self.policy.minimum_sectors_ready:
            return (
                SectorLeadershipGovernanceStatus.REVIEW,
                [
                    f"governed sector count {governed_sector_count} < "
                    f"{self.policy.minimum_sectors_ready}"
                ],
            )

        return SectorLeadershipGovernanceStatus.READY, []

    @staticmethod
    def _classification(symbol: str) -> str:
        if symbol in OFFENSIVE_SECTORS:
            return "OFFENSIVE"
        if symbol in DEFENSIVE_SECTORS:
            return "DEFENSIVE"
        if symbol in CYCLICAL_SECTORS:
            return "CYCLICAL"
        return "OTHER"

    @staticmethod
    def _float(value: Any) -> float | None:
        return float(value) if value is not None else None
