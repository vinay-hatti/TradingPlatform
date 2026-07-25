from __future__ import annotations
import json
from datetime import date
from sqlalchemy import Boolean, Date, Float, ForeignKeyConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from trading_ai.database.base import Base

class DealerPositionSnapshotModel(Base):
    __tablename__='dealer_position_snapshot'
    symbol:Mapped[str]=mapped_column(String(16),primary_key=True)
    as_of_date:Mapped[date]=mapped_column(Date,primary_key=True)
    quote_date:Mapped[date]=mapped_column(Date,nullable=False,index=True)
    spot_price:Mapped[float]=mapped_column(Float,nullable=False)
    source_table:Mapped[str]=mapped_column(String(128),nullable=False)
    dealer_sign_convention:Mapped[str]=mapped_column(String(32),nullable=False)
    estimator_name:Mapped[str]=mapped_column(String(96),nullable=False)
    estimator_version:Mapped[str]=mapped_column(String(24),nullable=False)
    source_contract_count:Mapped[int]=mapped_column(Integer,nullable=False)
    executable_contract_count:Mapped[int]=mapped_column(Integer,nullable=False)
    quote_coverage_pct:Mapped[float]=mapped_column(Float,nullable=False)
    unsigned_gamma_exposure:Mapped[float]=mapped_column(Float,nullable=False)
    unsigned_delta_exposure:Mapped[float]=mapped_column(Float,nullable=False)
    net_gamma_exposure:Mapped[float]=mapped_column(Float,nullable=False)
    net_delta_exposure:Mapped[float]=mapped_column(Float,nullable=False)
    net_vanna_exposure:Mapped[float]=mapped_column(Float,nullable=False)
    net_charm_exposure:Mapped[float]=mapped_column(Float,nullable=False)
    gamma_regime:Mapped[str]=mapped_column(String(32),nullable=False)
    gamma_flip:Mapped[float|None]=mapped_column(Float)
    gamma_flip_distance_pct:Mapped[float|None]=mapped_column(Float)
    gamma_flip_confidence:Mapped[float]=mapped_column(Float,nullable=False)
    primary_call_wall:Mapped[float|None]=mapped_column(Float)
    secondary_call_wall:Mapped[float|None]=mapped_column(Float)
    primary_put_wall:Mapped[float|None]=mapped_column(Float)
    secondary_put_wall:Mapped[float|None]=mapped_column(Float)
    magnet_strike:Mapped[float|None]=mapped_column(Float)
    expected_move:Mapped[float|None]=mapped_column(Float)
    expected_move_pct:Mapped[float|None]=mapped_column(Float)
    atm_iv:Mapped[float|None]=mapped_column(Float)
    iv_term_slope:Mapped[float|None]=mapped_column(Float)
    put_skew:Mapped[float|None]=mapped_column(Float)
    call_skew:Mapped[float|None]=mapped_column(Float)
    institutional_positioning_score:Mapped[float]=mapped_column(Float,nullable=False)
    positioning_label:Mapped[str]=mapped_column(String(32),nullable=False)
    bull_probability:Mapped[float]=mapped_column(Float,nullable=False)
    bear_probability:Mapped[float]=mapped_column(Float,nullable=False)
    range_probability:Mapped[float]=mapped_column(Float,nullable=False)
    breakout_probability:Mapped[float]=mapped_column(Float,nullable=False)
    breakdown_probability:Mapped[float]=mapped_column(Float,nullable=False)
    volatility_expansion_probability:Mapped[float]=mapped_column(Float,nullable=False)
    volatility_compression_probability:Mapped[float]=mapped_column(Float,nullable=False)
    confidence:Mapped[str]=mapped_column(String(16),nullable=False)
    confidence_score:Mapped[float]=mapped_column(Float,nullable=False)
    warnings_json:Mapped[str]=mapped_column(Text,nullable=False)
    assumptions_json:Mapped[str]=mapped_column(Text,nullable=False)
    provenance_json:Mapped[str]=mapped_column(Text,nullable=False)
    payload_json:Mapped[str]=mapped_column(Text,nullable=False)

    @classmethod
    def from_snapshot(cls,s):
        return cls(symbol=s.symbol,as_of_date=date.fromisoformat(s.as_of_date),quote_date=date.fromisoformat(s.option_snapshot_date),spot_price=s.spot,source_table=s.source_table,dealer_sign_convention=s.dealer_sign_convention,estimator_name=s.estimator_name,estimator_version=s.estimator_version,source_contract_count=s.source_contract_count,executable_contract_count=s.executable_contract_count,quote_coverage_pct=s.quote_coverage_pct,unsigned_gamma_exposure=s.unsigned_gamma_exposure,unsigned_delta_exposure=s.unsigned_delta_exposure,net_gamma_exposure=s.net_gamma_exposure,net_delta_exposure=s.net_delta_exposure,net_vanna_exposure=s.net_vanna_exposure,net_charm_exposure=s.net_charm_exposure,gamma_regime=s.gamma_regime,gamma_flip=s.gamma_flip,gamma_flip_distance_pct=s.gamma_flip_distance_pct,gamma_flip_confidence=s.gamma_flip_confidence,primary_call_wall=s.primary_call_wall,secondary_call_wall=s.secondary_call_wall,primary_put_wall=s.primary_put_wall,secondary_put_wall=s.secondary_put_wall,magnet_strike=s.magnet_strike,expected_move=s.expected_move,expected_move_pct=s.expected_move_pct,atm_iv=s.atm_iv,iv_term_slope=s.iv_term_slope,put_skew=s.put_skew,call_skew=s.call_skew,institutional_positioning_score=s.institutional_positioning_score,positioning_label=s.positioning_label,bull_probability=s.bull_probability,bear_probability=s.bear_probability,range_probability=s.range_probability,breakout_probability=s.breakout_probability,breakdown_probability=s.breakdown_probability,volatility_expansion_probability=s.volatility_expansion_probability,volatility_compression_probability=s.volatility_compression_probability,confidence=s.confidence,confidence_score=s.confidence_score,warnings_json=json.dumps(s.warnings),assumptions_json=json.dumps(s.assumptions),provenance_json=json.dumps([x.__dict__ for x in s.provenance]),payload_json=json.dumps(s.to_dict(),allow_nan=False))

class DealerStrikeProfileModel(Base):
    __tablename__='dealer_strike_profile'
    symbol:Mapped[str]=mapped_column(String(16),primary_key=True)
    as_of_date:Mapped[date]=mapped_column(Date,primary_key=True)
    expiry:Mapped[date]=mapped_column(Date,primary_key=True)
    strike:Mapped[float]=mapped_column(Float,primary_key=True)
    dte:Mapped[int]=mapped_column(Integer,nullable=False)
    call_open_interest:Mapped[float]=mapped_column(Float,nullable=False); put_open_interest:Mapped[float]=mapped_column(Float,nullable=False)
    call_volume:Mapped[float]=mapped_column(Float,nullable=False); put_volume:Mapped[float]=mapped_column(Float,nullable=False)
    call_gamma_exposure:Mapped[float]=mapped_column(Float,nullable=False); put_gamma_exposure:Mapped[float]=mapped_column(Float,nullable=False); net_gamma_exposure:Mapped[float]=mapped_column(Float,nullable=False)
    call_delta_exposure:Mapped[float]=mapped_column(Float,nullable=False); put_delta_exposure:Mapped[float]=mapped_column(Float,nullable=False); net_delta_exposure:Mapped[float]=mapped_column(Float,nullable=False)
    vanna_exposure:Mapped[float]=mapped_column(Float,nullable=False); charm_exposure:Mapped[float]=mapped_column(Float,nullable=False)
    call_spread_pct:Mapped[float|None]=mapped_column(Float); put_spread_pct:Mapped[float|None]=mapped_column(Float)
    liquidity_score:Mapped[float]=mapped_column(Float,nullable=False); dealer_pressure_score:Mapped[float]=mapped_column(Float,nullable=False); pin_score:Mapped[float]=mapped_column(Float,nullable=False)
    market_structure_eligible:Mapped[bool]=mapped_column(Boolean,nullable=False); trade_eligible:Mapped[bool]=mapped_column(Boolean,nullable=False)

class DealerExpirationProfileModel(Base):
    __tablename__='dealer_expiration_profile'
    symbol:Mapped[str]=mapped_column(String(16),primary_key=True); as_of_date:Mapped[date]=mapped_column(Date,primary_key=True); expiry:Mapped[date]=mapped_column(Date,primary_key=True)
    dte:Mapped[int]=mapped_column(Integer,nullable=False); call_open_interest:Mapped[float]=mapped_column(Float,nullable=False); put_open_interest:Mapped[float]=mapped_column(Float,nullable=False)
    net_gamma_exposure:Mapped[float]=mapped_column(Float,nullable=False); net_delta_exposure:Mapped[float]=mapped_column(Float,nullable=False); net_vanna_exposure:Mapped[float]=mapped_column(Float,nullable=False); net_charm_exposure:Mapped[float]=mapped_column(Float,nullable=False)
    atm_implied_volatility:Mapped[float|None]=mapped_column(Float); expected_move:Mapped[float|None]=mapped_column(Float); liquidity_score:Mapped[float]=mapped_column(Float,nullable=False)

class IVSurfaceSnapshotModel(Base):
    __tablename__='iv_surface_snapshot'
    symbol:Mapped[str]=mapped_column(String(16),primary_key=True); as_of_date:Mapped[date]=mapped_column(Date,primary_key=True); expiry:Mapped[date]=mapped_column(Date,primary_key=True); strike:Mapped[float]=mapped_column(Float,primary_key=True); option_type:Mapped[str]=mapped_column(String(8),primary_key=True)
    dte:Mapped[int]=mapped_column(Integer,nullable=False); moneyness:Mapped[float]=mapped_column(Float,nullable=False); delta:Mapped[float|None]=mapped_column(Float); implied_volatility:Mapped[float]=mapped_column(Float,nullable=False); bid:Mapped[float]=mapped_column(Float,nullable=False); ask:Mapped[float]=mapped_column(Float,nullable=False); mid:Mapped[float]=mapped_column(Float,nullable=False); spread_pct:Mapped[float|None]=mapped_column(Float)

# Backward-compatible alias for existing imports.
InstitutionalMarketStructureModel=DealerPositionSnapshotModel
