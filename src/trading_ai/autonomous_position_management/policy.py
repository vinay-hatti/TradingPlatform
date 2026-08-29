
from __future__ import annotations
from dataclasses import dataclass
import os


def _bool(value: str | None, default: bool) -> bool:
    if value is None:return default
    return str(value).strip().lower() in {'1','true','yes','on'}

def _float(value: str | None, default: float) -> float:
    try:return float(value) if value is not None else default
    except (TypeError,ValueError):return default

@dataclass(frozen=True)
class M73Policy:
    enabled: bool=True
    default_automation_mode: str='FULLY_AUTOMATIC'
    max_quote_age_seconds: float=30.0
    max_manager_heartbeat_age_seconds: float=180.0
    stale_working_order_seconds: float=45.0
    max_reprice_attempts: int=4
    max_spread_pct_profit: float=35.0
    max_spread_pct_defensive: float=75.0
    broker_emergency_protection_enabled: bool=True
    emergency_option_loss_fraction: float=0.55
    dynamic_target_migration_enabled: bool=True
    stop_may_loosen: bool=False
    paper_only: bool=True


def load_m73_policy() -> M73Policy:
    get=os.getenv
    return M73Policy(
        enabled=_bool(get('TRADING_AI_M73_ENABLED'),True),
        default_automation_mode=str(get('TRADING_AI_POSITION_MANAGEMENT_MODE') or 'FULLY_AUTOMATIC').upper(),
        max_quote_age_seconds=_float(get('TRADING_AI_M73_MAX_QUOTE_AGE_SECONDS'),30.0),
        max_manager_heartbeat_age_seconds=_float(get('TRADING_AI_M73_MAX_MANAGER_HEARTBEAT_AGE_SECONDS'),180.0),
        stale_working_order_seconds=_float(get('TRADING_AI_M73_STALE_WORKING_ORDER_SECONDS'),45.0),
        max_reprice_attempts=int(_float(get('TRADING_AI_M73_MAX_REPRICE_ATTEMPTS'),4)),
        max_spread_pct_profit=_float(get('TRADING_AI_M73_MAX_SPREAD_PCT_PROFIT'),35.0),
        max_spread_pct_defensive=_float(get('TRADING_AI_M73_MAX_SPREAD_PCT_DEFENSIVE'),75.0),
        broker_emergency_protection_enabled=_bool(get('TRADING_AI_M73_BROKER_EMERGENCY_PROTECTION_ENABLED'),True),
        emergency_option_loss_fraction=_float(get('TRADING_AI_M73_EMERGENCY_OPTION_LOSS_FRACTION'),0.55),
        dynamic_target_migration_enabled=_bool(get('TRADING_AI_M73_DYNAMIC_TARGET_MIGRATION_ENABLED'),True),
        stop_may_loosen=_bool(get('TRADING_AI_M73_STOP_MAY_LOOSEN'),False),
        paper_only=_bool(get('TRADING_AI_M73_PAPER_ONLY'),True),
    )
