from __future__ import annotations
from collections import defaultdict
from .portfolio_risk_policy import PortfolioRiskPolicy
from .portfolio_risk_profile import (
    PortfolioExposureProfile, PortfolioPositionProfile, PortfolioSnapshotProfile,
    SectorExposureProfile, SymbolExposureProfile,
)
from .pretrade_risk_profile import PreTradeRiskRequest

def _direction(side: str) -> float:
    return -1.0 if side.upper().startswith("SELL") else 1.0

def _position_exposure(position: PortfolioPositionProfile) -> float:
    if position.signed_exposure is not None:
        return float(position.signed_exposure)
    return float(position.quantity) * float(position.market_price) * max(int(position.multiplier or 1), 1)

class PortfolioExposureEngine:
    def __init__(self, policy: PortfolioRiskPolicy | None = None) -> None:
        self.policy = policy or PortfolioRiskPolicy()
        self.policy.validate()

    def calculate(self, order: PreTradeRiskRequest, snapshot: PortfolioSnapshotProfile) -> PortfolioExposureProfile:
        current_symbol_exposure = defaultdict(float)
        current_symbol_quantity = defaultdict(float)
        symbol_sector = {}
        symbol_asset_class = {}
        current_bp_usage = 0.0

        for position in snapshot.positions:
            exposure = _position_exposure(position)
            current_symbol_exposure[position.symbol] += exposure
            current_symbol_quantity[position.symbol] += position.quantity
            symbol_sector[position.symbol] = position.sector
            symbol_asset_class[position.symbol] = position.asset_class.upper()
            current_bp_usage += abs(position.buying_power_usage) if position.buying_power_usage is not None else abs(exposure)

        order_symbol_exposure = defaultdict(float)
        order_symbol_quantity = defaultdict(float)
        for leg in order.legs:
            price = float(leg.price or 0.0)
            multiplier = max(int(leg.multiplier or 1), 1)
            direction = _direction(leg.side)
            signed_quantity = direction * float(leg.quantity)
            signed_exposure = signed_quantity * price * multiplier
            order_symbol_quantity[leg.symbol] += signed_quantity
            order_symbol_exposure[leg.symbol] += signed_exposure
            symbol_asset_class.setdefault(leg.symbol, leg.asset_class.upper())
            symbol_sector.setdefault(leg.symbol, leg.metadata.get("sector"))

        all_symbols = sorted(set(current_symbol_exposure) | set(order_symbol_exposure))
        symbol_profiles = []
        for symbol in all_symbols:
            current_quantity = current_symbol_quantity.get(symbol, 0.0)
            projected_quantity = current_quantity + order_symbol_quantity.get(symbol, 0.0)
            current_exposure = current_symbol_exposure.get(symbol, 0.0)
            order_exposure = order_symbol_exposure.get(symbol, 0.0)
            projected_exposure = current_exposure + order_exposure
            nlv = snapshot.account.net_liquidation
            pct_nlv = abs(projected_exposure) / nlv if nlv > 0 else None
            new_position = abs(current_quantity) < 1e-12 and abs(projected_quantity) >= 1e-12
            symbol_profiles.append(SymbolExposureProfile(
                symbol=symbol,
                sector=symbol_sector.get(symbol),
                asset_class=symbol_asset_class.get(symbol, "UNKNOWN"),
                current_quantity=current_quantity,
                projected_quantity=projected_quantity,
                current_exposure=current_exposure,
                order_exposure=order_exposure,
                projected_exposure=projected_exposure,
                pct_of_net_liquidation=pct_nlv,
                new_position=new_position,
            ))

        current_sector_exposure = defaultdict(float)
        order_sector_exposure = defaultdict(float)
        for profile in symbol_profiles:
            sector = profile.sector or "UNCLASSIFIED"
            current_sector_exposure[sector] += profile.current_exposure
            order_sector_exposure[sector] += profile.order_exposure

        sector_profiles = []
        for sector in sorted(set(current_sector_exposure) | set(order_sector_exposure)):
            current = current_sector_exposure.get(sector, 0.0)
            order_value = order_sector_exposure.get(sector, 0.0)
            projected = current + order_value
            nlv = snapshot.account.net_liquidation
            sector_profiles.append(SectorExposureProfile(
                sector=sector,
                current_exposure=current,
                order_exposure=order_value,
                projected_exposure=projected,
                pct_of_net_liquidation=abs(projected) / nlv if nlv > 0 else None,
            ))

        current_gross = sum(abs(value) for value in current_symbol_exposure.values())
        projected_gross = sum(abs(profile.projected_exposure) for profile in symbol_profiles)
        current_net = sum(current_symbol_exposure.values())
        projected_net = sum(profile.projected_exposure for profile in symbol_profiles)
        order_bp_usage = sum(abs(value) for value in order_symbol_exposure.values())
        projected_bp_usage = current_bp_usage + order_bp_usage
        buying_power = snapshot.account.buying_power

        current_open_positions = sum(1 for q in current_symbol_quantity.values() if abs(q) >= 1e-12)
        projected_open_positions = sum(1 for p in symbol_profiles if abs(p.projected_quantity) >= 1e-12)
        new_positions = sum(p.new_position for p in symbol_profiles)

        return PortfolioExposureProfile(
            current_gross_exposure=round(current_gross, 6),
            projected_gross_exposure=round(projected_gross, 6),
            current_net_exposure=round(current_net, 6),
            projected_net_exposure=round(projected_net, 6),
            current_buying_power_usage=round(current_bp_usage, 6),
            projected_buying_power_usage=round(projected_bp_usage, 6),
            current_buying_power_utilization=current_bp_usage / buying_power if buying_power > 0 else None,
            projected_buying_power_utilization=projected_bp_usage / buying_power if buying_power > 0 else None,
            projected_buying_power_remaining=round(buying_power - projected_bp_usage, 6),
            projected_excess_liquidity=round(snapshot.account.excess_liquidity - order_bp_usage, 6),
            current_open_positions=current_open_positions,
            projected_open_positions=projected_open_positions,
            new_positions=new_positions,
            symbols=tuple(symbol_profiles),
            sectors=tuple(sector_profiles),
        )
