from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping
from .instrument_policy import InstrumentMappingPolicy
from .instrument_profile import EquityInstrumentProfile, InstrumentMappingProfile, OptionInstrumentProfile

def _value(obj: Any, name: str, default: Any = None) -> Any:
    return obj.get(name, default) if isinstance(obj, Mapping) else getattr(obj, name, default)

def _symbol(value: Any) -> str:
    return str(value or "").strip().upper()

def _expiry(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))

def build_occ_symbol(underlying_symbol: str, expiration: date, option_type: str, strike: float) -> str:
    root = _symbol(underlying_symbol)
    if not root:
        raise ValueError("underlying_symbol is required")
    cp = "C" if option_type.upper() == "CALL" else "P"
    strike_int = int((Decimal(str(strike)) * Decimal("1000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return f"{root:<6}{expiration:%y%m%d}{cp}{strike_int:08d}"

class InstrumentMapper:
    def __init__(self, policy=None, *, equity_symbol_map=None, option_symbol_map=None) -> None:
        self.policy = policy or InstrumentMappingPolicy()
        self.policy.validate()
        self.equity_symbol_map = {_symbol(k): str(v).strip() for k, v in (equity_symbol_map or {}).items()}
        self.option_symbol_map = {str(k).strip().upper(): str(v).strip() for k, v in (option_symbol_map or {}).items()}

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95: return "A", "LOW"
        if score >= 85: return "B", "MODERATE"
        if score >= 70: return "C", "SEVERE"
        return "F", "CRITICAL"

    def map_equity(self, value: Any) -> InstrumentMappingProfile:
        symbol = _symbol(_value(value, "symbol", _value(value, "underlying_symbol", "")))
        reasons = []
        if not symbol:
            reasons.append("SYMBOL_REQUIRED")
        broker_symbol = self.equity_symbol_map.get(symbol, _symbol(_value(value, "broker_symbol", symbol)))
        if not broker_symbol:
            reasons.append("BROKER_SYMBOL_REQUIRED")
        score = max(0.0, 100.0 - 50.0 * len(reasons))
        grade, severity = self._grade(score)
        equity = None if reasons else EquityInstrumentProfile(
            symbol=symbol, broker_symbol=broker_symbol, exchange=_value(value, "exchange"),
            currency=str(_value(value, "currency", "USD")).upper(),
            metadata=dict(_value(value, "metadata", {}) or {}),
        )
        return InstrumentMappingProfile(True, not reasons, "EQUITY", symbol, broker_symbol or None, equity=equity,
            score=score, grade=grade, severity=severity, recommendation="USE" if not reasons else "REJECT",
            rejection_reasons=tuple(reasons))

    def map_option(self, value: Any) -> InstrumentMappingProfile:
        underlying = _symbol(_value(value, "underlying_symbol", _value(value, "symbol", "")))
        expiration = _expiry(_value(value, "expiration", _value(value, "expiry")))
        option_type = str(_value(value, "option_type", _value(value, "right", ""))).strip().upper()
        try:
            strike = float(_value(value, "strike"))
        except (TypeError, ValueError):
            strike = 0.0
        multiplier = int(_value(value, "multiplier", self.policy.default_option_multiplier) or self.policy.default_option_multiplier)
        reasons = []
        if self.policy.require_underlying_symbol and not underlying: reasons.append("UNDERLYING_SYMBOL_REQUIRED")
        if self.policy.require_option_expiration and expiration is None: reasons.append("OPTION_EXPIRATION_REQUIRED")
        if self.policy.require_option_type and option_type not in self.policy.allowed_option_types: reasons.append("OPTION_TYPE_INVALID")
        if self.policy.require_option_strike and strike < self.policy.minimum_strike: reasons.append("OPTION_STRIKE_INVALID")
        if multiplier <= 0 or multiplier > self.policy.maximum_contract_multiplier: reasons.append("OPTION_MULTIPLIER_INVALID")
        if expiration and self.policy.reject_expired_options and expiration < date.today(): reasons.append("OPTION_EXPIRED")
        occ = build_occ_symbol(underlying, expiration, option_type, strike) if not reasons else None
        broker_underlying = self.equity_symbol_map.get(underlying, underlying)
        broker_symbol = self.option_symbol_map.get(occ.upper()) if occ else None
        if broker_symbol is None and occ:
            broker_symbol = str(_value(value, "broker_symbol", occ)).strip()
        score = max(0.0, 100.0 - 20.0 * len(reasons))
        grade, severity = self._grade(score)
        option = None if reasons else OptionInstrumentProfile(
            underlying_symbol=underlying, broker_underlying_symbol=broker_underlying,
            expiration=expiration.isoformat(), strike=strike, option_type=option_type,
            multiplier=multiplier, occ_symbol=occ, broker_symbol=broker_symbol,
            exchange=_value(value, "exchange"), currency=str(_value(value, "currency", "USD")).upper(),
            metadata=dict(_value(value, "metadata", {}) or {}),
        )
        return InstrumentMappingProfile(True, not reasons, "OPTION", occ or underlying, broker_symbol,
            option=option, score=score, grade=grade, severity=severity,
            recommendation="USE" if not reasons else "REJECT", rejection_reasons=tuple(reasons))

    def map(self, value: Any) -> InstrumentMappingProfile:
        asset_class = str(_value(value, "asset_class", "EQUITY")).strip().upper()
        if asset_class == "EQUITY": return self.map_equity(value)
        if asset_class == "OPTION": return self.map_option(value)
        return InstrumentMappingProfile(True, False, asset_class, "", None, score=0.0, grade="F",
            severity="CRITICAL", recommendation="REJECT", rejection_reasons=("ASSET_CLASS_NOT_SUPPORTED",))
