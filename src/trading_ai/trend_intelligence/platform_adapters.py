from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from trading_ai.trend_intelligence.platform_integration import (
    TrendPlatformContext,
    TrendPlatformIntegrationService,
)


@dataclass(frozen=True)
class TrendScannerAdapter:
    service: TrendPlatformIntegrationService

    def enrich(self, symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
        context = self.service.context(symbol)
        result = dict(payload)
        result.update({
            "trend_platform_status": context.status,
            "trend_platform_adjustment": context.scanner_adjustment,
            "trend_platform_context": context.to_dict(),
        })
        return result


@dataclass(frozen=True)
class TrendDecisionAdapter:
    service: TrendPlatformIntegrationService

    def enrich(self, symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
        context = self.service.context(symbol)
        result = dict(payload)
        result.update({
            "trend_decision_adjustment": context.decision_adjustment,
            "trend_decision_context": context.to_dict(),
        })
        return result


@dataclass(frozen=True)
class TrendPortfolioRiskAdapter:
    service: TrendPlatformIntegrationService

    def enrich(self, symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
        context = self.service.context(symbol)
        result = dict(payload)
        result.update({
            "trend_portfolio_risk_adjustment": context.portfolio_risk_adjustment,
            "trend_portfolio_risk_context": context.to_dict(),
        })
        return result


@dataclass(frozen=True)
class TrendMarketOverviewAdapter:
    service: TrendPlatformIntegrationService

    def build(self, symbols: Iterable[str]) -> dict[str, Any]:
        return self.service.market_overview(symbols)
