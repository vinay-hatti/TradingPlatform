from dataclasses import asdict

from trading_ai.stock_intelligence.levels import LevelIntelligenceService
from trading_ai.stock_intelligence.models import (
    StockSupportResistanceLevelModel,
    StockSupplyDemandZoneModel,
)
from trading_ai.stock_intelligence.profile import PriceLevel


def _bars(start=100.0, count=140, step=0.15):
    rows=[]
    price=start
    for index in range(count):
        close=price + (index % 9 - 4) * 0.08
        rows.append({
            "open": close - 0.1,
            "high": close + 0.6,
            "low": close - 0.6,
            "close": close,
            "volume": 100000 + index * 250,
        })
        price += step
    return rows


def test_level_contributors_are_deduplicated_and_primary_is_structural():
    result=LevelIntelligenceService().analyze({"1d":_bars(),"1w":_bars(step=0.8),"1mo":_bars(step=2.0)})
    levels=result["support_levels"]+result["resistance_levels"]
    assert levels
    for level in levels:
        assert len(level.contributing_timeframes)==len(set(level.contributing_timeframes))
        assert level.timeframe in level.contributing_timeframes
        assert "," not in level.timeframe
        assert len(level.timeframe)<=16


def test_price_level_serialization_exposes_structured_timeframes():
    level=PriceLevel("SUPPORT",100.0,"1w",85.0,contributing_timeframes=["1w","1d"])
    payload=asdict(level)
    assert payload["timeframe"]=="1w"
    assert payload["contributing_timeframes"]==["1w","1d"]
    assert level.primary_timeframe=="1w"


def test_sqlalchemy_models_have_structured_timeframe_columns():
    for model in (StockSupportResistanceLevelModel,StockSupplyDemandZoneModel):
        assert "primary_timeframe" in model.__table__.columns
        assert "contributing_timeframes" in model.__table__.columns
        assert model.__table__.columns["timeframe"].type.length==32
