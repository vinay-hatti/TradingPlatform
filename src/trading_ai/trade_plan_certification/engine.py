from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Iterable

CERTIFICATION_VERSION = 'M68.2.1-CONDITIONAL-ENTRY-GOVERNANCE-1.0'


def _f(value: Any) -> float | None:
    try:
        x = float(value)
        return x if isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _direction(value: Any) -> str:
    text = str(value or '').upper()
    if 'BULL' in text:
        return 'BULLISH'
    if 'BEAR' in text:
        return 'BEARISH'
    return 'NEUTRAL'


def _age_minutes(timestamp: str | None) -> float | None:
    if not timestamp:
        return None
    try:
        dt = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 60.0)
    except ValueError:
        return None


def _rule(code: str, passed: bool, message: str, *, severity: str = 'ERROR', evidence: dict | None = None) -> dict:
    return {
        'code': code,
        'status': 'PASS' if passed else 'FAIL',
        'severity': severity,
        'message': message,
        'evidence': dict(evidence or {}),
    }


def _domain(name: str, rules: list[dict], *, not_applicable: bool = False) -> dict:
    if not_applicable:
        return {'name': name, 'status': 'NOT_APPLICABLE', 'score': 100.0, 'rules': rules}
    blocking = [r for r in rules if r.get('severity') == 'ERROR']
    passed = all(r.get('status') == 'PASS' for r in blocking)
    if not rules:
        score = 100.0
    else:
        score = round(sum(1 for r in rules if r.get('status') == 'PASS') / len(rules) * 100.0, 2)
    return {'name': name, 'status': 'PASS' if passed else 'FAIL', 'score': score, 'rules': rules}


def _canonical_number(value: Any) -> float | None:
    x = _f(value)
    return None if x is None else round(x, 8)


def plan_fingerprint(
    *,
    direction: Any,
    reference_market: dict | None,
    entry_zone_low: Any,
    entry_zone_high: Any,
    structural_stop: Any,
    targets: Iterable[Any],
    strategy: str | None = None,
    legs: Iterable[dict] | None = None,
    dynamic_management: dict | None = None,
    risk: dict | None = None,
) -> str:
    """Stable SHA-256 binding for the exact governed plan represented downstream."""
    reference = dict(reference_market or {})
    canonical_legs = []
    for raw in legs or ():
        leg = dict(raw)
        canonical_legs.append({
            'side': str(leg.get('side') or '').upper(),
            'quantity': int(leg.get('quantity') or leg.get('quantity_ratio') or 0),
            'option_right': str(leg.get('option_right') or leg.get('option_type') or '').upper(),
            'strike': _canonical_number(leg.get('strike')),
            'expiry': str(leg.get('expiry') or ''),
            'option_symbol': str(leg.get('option_symbol') or ''),
        })
    canonical_legs.sort(key=lambda x: (x['side'], x['expiry'], x['strike'] or 0, x['option_symbol']))
    dm = dict(dynamic_management or {})
    payload = {
        'direction': _direction(direction),
        'reference_market': {
            'price': _canonical_number(reference.get('price')),
            'timestamp': str(reference.get('timestamp') or ''),
            'source': str(reference.get('source') or ''),
            'provider': str(reference.get('provider') or ''),
        },
        'underlying_plan': {
            'entry_zone_low': _canonical_number(entry_zone_low),
            'entry_zone_high': _canonical_number(entry_zone_high),
            'structural_stop': _canonical_number(structural_stop),
            'targets': [_canonical_number(x) for x in targets],
        },
        'strategy': str(strategy or '').upper(),
        'legs': canonical_legs,
        'management': {
            'trailing_policy': str(dm.get('trailing_policy') or ''),
            'emergency_option_stop_pct': _canonical_number(dm.get('emergency_option_stop_pct')),
            'theta_exit_days_to_expiry': int(dm.get('theta_exit_days_to_expiry') or 0),
            'volatility_exit_rule': str(dm.get('volatility_exit_rule') or ''),
            'assignment_risk_rule': str(dm.get('assignment_risk_rule') or ''),
            'management_mode': str(dm.get('management_mode') or ''),
        },
        'risk': dict(risk or {}),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return sha256(blob.encode('utf-8')).hexdigest()


def _reference_market(profile: Any) -> dict:
    states = getattr(profile, 'timeframe_states', {}) or {}
    primary = str(getattr(profile, 'primary_timeframe', '1d') or '1d')
    state = states.get(primary)
    if state is None and states:
        state = next(iter(states.values()))
    price = _f(getattr(state, 'close', None))
    ts = str(getattr(profile, 'snapshot_timestamp', '') or '') or None
    age = _age_minutes(ts)
    return {
        'price': price,
        'timestamp': ts,
        'freshness_minutes_at_certification': None if age is None else round(age, 2),
        'source': 'LATEST_UNDERLYING_INGESTION',
        'provider': str(getattr(profile, 'provider', 'polygon') or 'polygon').upper(),
        'primary_timeframe': primary,
    }


def _geometry_rules(*, direction: str, ref: float | None, entry_low: float | None, entry_high: float | None, stop_price: float | None, targets: list[float]) -> list[dict]:
    rules: list[dict] = []
    rules.append(_rule('TPC-GEO-000', direction in {'BULLISH', 'BEARISH'}, 'Trade plan must have a directional bullish or bearish thesis.', evidence={'direction': direction}))
    rules.append(_rule('TPC-GEO-004', entry_low is not None and entry_high is not None and entry_low > 0 and entry_high >= entry_low, 'Entry zone must be positive and ordered.', evidence={'entry_zone_low': entry_low, 'entry_zone_high': entry_high}))
    if direction == 'BULLISH':
        invalid = [x for x in targets if ref is None or x <= ref]
        rules.append(_rule('TPC-GEO-001', bool(targets) and not invalid, 'Every bullish target must be strictly above the reference underlying price.', evidence={'reference_price': ref, 'targets': targets, 'invalid_targets': invalid}))
        monotonic = all(targets[i] < targets[i + 1] for i in range(len(targets) - 1))
        rules.append(_rule('TPC-GEO-003', bool(targets) and monotonic, 'Bullish targets must be strictly increasing.', evidence={'targets': targets}))
        rules.append(_rule('TPC-GEO-005', stop_price is not None and ref is not None and stop_price < ref, 'Bullish structural stop must be below the reference price.', evidence={'stop': stop_price, 'reference_price': ref}))
        rules.append(_rule('TPC-GEO-006', stop_price is not None and entry_low is not None and stop_price < entry_low, 'Bullish structural stop must be below the entry zone.', evidence={'stop': stop_price, 'entry_zone_low': entry_low}))
        rules.append(_rule('TPC-GEO-007', bool(targets) and entry_high is not None and targets[0] > entry_high, 'Bullish Target 1 must be above the entry zone.', evidence={'target_1': targets[0] if targets else None, 'entry_zone_high': entry_high}))
    elif direction == 'BEARISH':
        invalid = [x for x in targets if ref is None or x >= ref]
        rules.append(_rule('TPC-GEO-002', bool(targets) and not invalid, 'Every bearish target must be strictly below the reference underlying price.', evidence={'reference_price': ref, 'targets': targets, 'invalid_targets': invalid}))
        monotonic = all(targets[i] > targets[i + 1] for i in range(len(targets) - 1))
        rules.append(_rule('TPC-GEO-003', bool(targets) and monotonic, 'Bearish targets must be strictly decreasing.', evidence={'targets': targets}))
        rules.append(_rule('TPC-GEO-005', stop_price is not None and ref is not None and stop_price > ref, 'Bearish structural stop must be above the reference price.', evidence={'stop': stop_price, 'reference_price': ref}))
        rules.append(_rule('TPC-GEO-006', stop_price is not None and entry_high is not None and stop_price > entry_high, 'Bearish structural stop must be above the entry zone.', evidence={'stop': stop_price, 'entry_zone_high': entry_high}))
        rules.append(_rule('TPC-GEO-007', bool(targets) and entry_low is not None and targets[0] < entry_low, 'Bearish Target 1 must be below the entry zone.', evidence={'target_1': targets[0] if targets else None, 'entry_zone_low': entry_low}))
    return rules


def _entry_execution_readiness(
    *,
    direction: str,
    reference_price: float | None,
    entry_policy: dict | None,
    targets: list[float],
    geometry_context: dict | None = None,
) -> dict:
    """Separate structural validity from immediate execution actionability."""
    policy = dict(entry_policy or {})
    geometry = dict(geometry_context or {})
    entry_type = str(
        policy.get('entry_type') or policy.get('kind') or 'UNSPECIFIED'
    ).upper()
    entry_low = _f(policy.get('zone_low'))
    entry_high = _f(policy.get('zone_high'))
    chase_limit = _f(policy.get('chase_limit'))
    confirmation_trigger = _f(policy.get('confirmation_trigger'))
    atr = _f(geometry.get('atr'))
    ref = reference_price
    target_1 = targets[0] if targets else None
    minimum_target_room = None if ref is None else max(
        abs(ref) * 0.005,
        0.0 if atr is None else abs(atr) * 0.25,
    )
    target_room = None
    if ref is not None and target_1 is not None:
        target_room = (
            target_1 - ref if direction == 'BULLISH' else ref - target_1
        )

    reasons: list[str] = []
    disposition = 'WAITING_FOR_ENTRY'
    if ref is None or entry_low is None or entry_high is None:
        disposition = 'REGENERATE_REQUIRED'
        reasons.append('ENTRY_ACTIONABILITY_INPUTS_MISSING')
    elif (
        target_room is None
        or minimum_target_room is None
        or target_room < minimum_target_room
    ):
        disposition = 'REGENERATE_REQUIRED'
        reasons.append('TARGET_1_REMAINING_ROOM_INSUFFICIENT')
    elif direction == 'BULLISH':
        upper = chase_limit if chase_limit is not None else entry_high
        if entry_low <= ref <= upper:
            disposition = 'READY_NOW'
            reasons.append('REFERENCE_PRICE_WITHIN_GOVERNED_ENTRY_RANGE')
        elif ref > upper:
            if confirmation_trigger is not None and ref >= confirmation_trigger:
                disposition = 'REGENERATE_REQUIRED'
                reasons.append('CONFIRMATION_TRIGGER_CROSSED_REBUILD_AT_CURRENT_MARKET')
            else:
                reasons.append('ABOVE_CHASE_LIMIT_WAIT_FOR_PULLBACK_OR_CONFIRMATION')
        else:
            reasons.append('BELOW_ENTRY_ZONE_WAIT_FOR_GOVERNED_TRIGGER')
    elif direction == 'BEARISH':
        lower = chase_limit if chase_limit is not None else entry_low
        if lower <= ref <= entry_high:
            disposition = 'READY_NOW'
            reasons.append('REFERENCE_PRICE_WITHIN_GOVERNED_ENTRY_RANGE')
        elif ref < lower:
            if confirmation_trigger is not None and ref <= confirmation_trigger:
                disposition = 'REGENERATE_REQUIRED'
                reasons.append('CONFIRMATION_TRIGGER_CROSSED_REBUILD_AT_CURRENT_MARKET')
            else:
                reasons.append('BELOW_CHASE_LIMIT_WAIT_FOR_RETEST_OR_CONFIRMATION')
        else:
            reasons.append('ABOVE_ENTRY_ZONE_WAIT_FOR_GOVERNED_TRIGGER')
    else:
        disposition = 'REGENERATE_REQUIRED'
        reasons.append('DIRECTIONAL_ENTRY_REQUIRED')

    return {
        'disposition': disposition,
        'trade_builder_ready': disposition == 'READY_NOW',
        'reason_codes': reasons,
        'entry_type': entry_type,
        'reference_price': ref,
        'entry_zone_low': entry_low,
        'entry_zone_high': entry_high,
        'confirmation_trigger': confirmation_trigger,
        'chase_limit': chase_limit,
        'target_1': target_1,
        'target_1_remaining_room': (
            None if target_room is None else round(target_room, 8)
        ),
        'minimum_target_1_room': (
            None if minimum_target_room is None
            else round(minimum_target_room, 8)
        ),
        'atr': atr,
    }


def certify_stock_trade_plan(profile: Any, plan: Any) -> dict:
    reference = _reference_market(profile)
    ref = _f(reference.get('price'))
    direction = _direction(getattr(profile, 'direction', None))
    entry = getattr(plan, 'entry', None)
    stop = getattr(plan, 'stop', None)
    target_profile = getattr(plan, 'targets', None)
    trailing = getattr(plan, 'trailing', None)
    exit_profile = getattr(plan, 'exit', None)
    entry_low = _f(getattr(entry, 'zone_low', None))
    entry_high = _f(getattr(entry, 'zone_high', None))
    stop_price = _f(getattr(stop, 'recommended_stop', None))
    targets = [_f(getattr(x, 'price', x)) for x in (getattr(target_profile, 'targets', None) or [])]
    targets = [x for x in targets if x is not None]

    market_rules = [
        _rule('TPC-MKT-001', ref is not None and ref > 0, 'Reference underlying price must be available from the latest ingestion.', evidence={'reference_price': ref}),
        _rule('TPC-MKT-002', bool(reference.get('timestamp')), 'Reference market timestamp must be present.', evidence={'timestamp': reference.get('timestamp')}),
        _rule('TPC-MKT-003', reference.get('provider') == 'POLYGON', 'Reference market lineage must be Polygon.', evidence={'provider': reference.get('provider')}),
    ]
    geo_rules = _geometry_rules(direction=direction, ref=ref, entry_low=entry_low, entry_high=entry_high, stop_price=stop_price, targets=targets)
    rr = _f(getattr(plan, 'structural_reward_risk', None))
    risk_rules = [
        _rule('TPC-RISK-001', rr is not None and rr > 0, 'Structural reward/risk must be positive.', evidence={'structural_reward_risk': rr}),
        _rule('TPC-RISK-002', stop_price is not None and stop_price > 0, 'Defined structural stop is required.', evidence={'stop': stop_price}),
    ]
    mgmt_rules = [
        _rule('TPC-MGMT-001', stop_price is not None and stop_price > 0, 'Structural stop must be available for autonomous management.'),
        _rule('TPC-MGMT-002', bool(targets), 'At least one governed profit target must be available.'),
        _rule('TPC-MGMT-003', bool(getattr(trailing, 'method', None)), 'Trailing policy must be defined.'),
        _rule('TPC-MGMT-004', bool(getattr(exit_profile, 'reason', None)), 'Underlying exit intelligence must be available.'),
    ]
    domains = {
        'market': _domain('MARKET', market_rules),
        'geometry': _domain('GEOMETRY', geo_rules),
        'risk': _domain('RISK', risk_rules),
        'management': _domain('AUTONOMOUS_MANAGEMENT', mgmt_rules),
        'strategy': _domain('STRATEGY', [], not_applicable=True),
        'execution': _domain('EXECUTION', [], not_applicable=True),
        'lifecycle': _domain('LIFECYCLE', [], not_applicable=True),
        'lineage': _domain('LINEAGE', [], not_applicable=True),
    }
    status = 'PASS' if all(x['status'] in {'PASS', 'NOT_APPLICABLE'} for x in domains.values()) else 'FAIL'
    freshness = reference.get('freshness_minutes_at_certification')
    freshness_score = 100.0 if freshness is None else max(0.0, 100.0 - min(100.0, float(freshness) / 14.4))
    scores = [domains[k]['score'] for k in ('market', 'geometry', 'risk', 'management')]
    quality = round(sum(scores) / len(scores) * 0.9 + freshness_score * 0.1, 2)
    failures = [r for d in domains.values() for r in d.get('rules', []) if r.get('status') == 'FAIL' and r.get('severity') == 'ERROR']
    entry_policy = {
        'entry_type': getattr(entry, 'entry_type', None),
        'preferred_entry': getattr(entry, 'preferred_entry', None),
        'zone_low': getattr(entry, 'zone_low', None),
        'zone_high': getattr(entry, 'zone_high', None),
        'confirmation_trigger': getattr(entry, 'confirmation_trigger', None),
        'chase_limit': getattr(entry, 'chase_limit', None),
    }
    entry_execution = _entry_execution_readiness(
        direction=direction,
        reference_price=ref,
        entry_policy=entry_policy,
        targets=targets,
        geometry_context=dict(getattr(plan, 'geometry_context', None) or {}),
    )
    fingerprint = plan_fingerprint(
        direction=direction, reference_market=reference, entry_zone_low=entry_low, entry_zone_high=entry_high,
        structural_stop=stop_price, targets=targets,
    )
    return {
        'certification_id': f"TPC-{getattr(profile, 'symbol', 'UNKNOWN')}-{str(getattr(profile, 'state_hash', '') or 'PENDING')[:12]}",
        'version': CERTIFICATION_VERSION,
        'certification_scope': 'STOCK_TRADE_PLAN',
        'status': status,
        'certified_at': datetime.now(timezone.utc).isoformat(),
        'reference_market': reference,
        'direction': direction,
        'quality_score': quality,
        'publishable': status == 'PASS',
        'trade_builder_ready': (
            status == 'PASS' and entry_execution['trade_builder_ready']
        ),
        'execution_disposition': entry_execution['disposition'],
        'entry_execution': entry_execution,
        'plan_fingerprint': fingerprint,
        'source_plan_fingerprint': fingerprint,
        'plan_mutated': False,
        'domains': domains,
        'failure_codes': [x['code'] for x in failures],
        'failure_reasons': [x['message'] for x in failures],
    }


def _strategy_rules(strategy: str, legs: list[dict]) -> list[dict]:
    name = str(strategy or '').upper()
    buys = [x for x in legs if str(x.get('side', '')).upper() == 'BUY']
    sells = [x for x in legs if str(x.get('side', '')).upper() == 'SELL']
    expiries = sorted({str(x.get('expiry') or '') for x in legs})
    rules = [
        _rule('TPC-STR-001', bool(legs), 'Strategy must contain at least one option leg.'),
        _rule('TPC-STR-002', all(bool(str(x.get('option_symbol') or '').strip()) for x in legs), 'Every option leg must carry exact Polygon contract identity.'),
    ]
    if name in {'LONG_CALL', 'LONG_PUT'}:
        rules.append(_rule('TPC-STR-010', len(legs) == 1 and len(buys) == 1, f'{name} must contain exactly one long option leg.'))
    elif name in {'BULL_CALL_SPREAD', 'BEAR_PUT_SPREAD'}:
        same_exp = len(expiries) == 1
        rules.append(_rule('TPC-STR-020', len(legs) == 2 and len(buys) == 1 and len(sells) == 1 and same_exp, f'{name} must contain one long and one short leg with the same expiry.'))
        if len(buys) == 1 and len(sells) == 1:
            b = _f(buys[0].get('strike')); s = _f(sells[0].get('strike'))
            valid = b is not None and s is not None and (b < s if name == 'BULL_CALL_SPREAD' else b > s)
            rules.append(_rule('TPC-STR-021', valid, f'{name} strike ordering is invalid.', evidence={'buy_strike': b, 'sell_strike': s}))
    elif name in {'CALL_DIAGONAL', 'PUT_DIAGONAL'}:
        rules.append(_rule('TPC-STR-030', len(legs) == 2 and len(buys) == 1 and len(sells) == 1 and len(expiries) == 2, f'{name} must contain one long and one short leg across two expirations.'))
        if len(buys) == 1 and len(sells) == 1:
            rules.append(_rule('TPC-STR-031', str(buys[0].get('expiry') or '') > str(sells[0].get('expiry') or ''), 'Diagonal long leg must expire after the short leg.', evidence={'long_expiry': buys[0].get('expiry'), 'short_expiry': sells[0].get('expiry')}))
    return rules


def certify_institutional_underlying_plan(
    *,
    stock_certification: dict | None,
    direction: Any,
    entry_zone_low: Any,
    entry_zone_high: Any,
    structural_stop: Any,
    targets: Iterable[Any],
    strategy: str,
    legs: Iterable[dict],
    contract_executable: bool,
    dynamic_management: dict | None,
    entry_policy: dict | None = None,
    geometry_context: dict | None = None,
) -> dict:
    """Re-certify the exact Institutional Options plan after strategy/management transformation."""
    base = dict(stock_certification or {})
    reference = dict(base.get('reference_market') or {})
    ref = _f(reference.get('price'))
    direction_value = _direction(direction)
    entry_low = _f(entry_zone_low); entry_high = _f(entry_zone_high); stop_price = _f(structural_stop)
    target_values = [_f(x) for x in targets]
    target_values = [x for x in target_values if x is not None]
    leg_values = [dict(x) for x in legs]
    dm = dict(dynamic_management or {})
    source_fp = str(base.get('plan_fingerprint') or base.get('source_plan_fingerprint') or '')
    final_fp = plan_fingerprint(
        direction=direction_value, reference_market=reference, entry_zone_low=entry_low, entry_zone_high=entry_high,
        structural_stop=stop_price, targets=target_values, strategy=strategy, legs=leg_values,
        dynamic_management=dm,
    )
    # Underlying-only comparison isolates whether Institutional Options changed the scanner plan geometry.
    final_underlying_fp = plan_fingerprint(
        direction=direction_value, reference_market=reference, entry_zone_low=entry_low, entry_zone_high=entry_high,
        structural_stop=stop_price, targets=target_values,
    )
    mutated = bool(source_fp and source_fp != final_underlying_fp)
    market_rules = [
        _rule('TPC-MKT-001', ref is not None and ref > 0, 'Reference underlying price must remain available from the certified Stock Intelligence plan.', evidence={'reference_price': ref}),
        _rule('TPC-MKT-002', bool(reference.get('timestamp')), 'Reference market timestamp must remain bound to the Institutional Options plan.', evidence={'timestamp': reference.get('timestamp')}),
        _rule('TPC-MKT-003', str(reference.get('provider') or '').upper() == 'POLYGON', 'Reference market lineage must remain Polygon.', evidence={'provider': reference.get('provider')}),
    ]
    geo_rules = _geometry_rules(direction=direction_value, ref=ref, entry_low=entry_low, entry_high=entry_high, stop_price=stop_price, targets=target_values)
    entry_mid = None if entry_low is None or entry_high is None else (entry_low + entry_high) / 2.0
    rr = None
    if entry_mid is not None and stop_price is not None and target_values:
        rr = abs(target_values[0] - entry_mid) / max(abs(entry_mid - stop_price), 1e-9)
    risk_rules = [
        _rule('TPC-RISK-001', rr is not None and rr > 0, 'Institutional underlying reward/risk must remain positive after transformation.', evidence={'structural_reward_risk': rr}),
        _rule('TPC-RISK-002', stop_price is not None and stop_price > 0, 'Institutional underlying plan must retain a defined structural stop.', evidence={'stop': stop_price}),
    ]
    strategy_domain = _domain('STRATEGY', _strategy_rules(strategy, leg_values))
    execution_rules = [
        _rule('TPC-EXEC-020', bool(contract_executable), 'Selected Institutional Options contract recommendation must be executable.'),
        _rule('TPC-EXEC-021', all(bool(str(x.get('option_symbol') or '').strip()) for x in leg_values), 'Final Institutional Options plan must retain exact contract identity.'),
    ]
    mgmt_rules = [
        _rule('TPC-MGMT-010', stop_price is not None, 'Institutional Options management plan must retain the structural stop.'),
        _rule('TPC-MGMT-011', bool(target_values), 'Institutional Options management plan must retain governed underlying targets.'),
        _rule('TPC-MGMT-012', bool(dm.get('trailing_policy')), 'Institutional Options management plan must define trailing policy.'),
        _rule('TPC-MGMT-013', bool(dm.get('volatility_exit_rule')), 'Institutional Options management plan must define volatility exit governance.'),
    ]
    lineage_rules = [
        _rule('TPC-LIN-001', base.get('status') == 'PASS', 'Source Stock Intelligence trade plan certification must PASS.', evidence={'source_status': base.get('status')}),
        _rule('TPC-LIN-002', bool(source_fp), 'Source Stock Intelligence plan fingerprint must be present.', evidence={'source_plan_fingerprint': source_fp}),
        _rule('TPC-LIN-003', bool(final_fp), 'Final Institutional Options plan fingerprint must be materialized.', evidence={'plan_fingerprint': final_fp}),
        _rule('TPC-LIN-004', True, 'Any downstream plan mutation is explicitly re-certified before readiness.', severity='INFO', evidence={'plan_mutated': mutated}),
    ]
    domains = {
        'market': _domain('MARKET', market_rules),
        'geometry': _domain('GEOMETRY', geo_rules),
        'risk': _domain('RISK', risk_rules),
        'strategy': strategy_domain,
        'execution': _domain('EXECUTION', execution_rules),
        'management': _domain('AUTONOMOUS_MANAGEMENT', mgmt_rules),
        'lifecycle': _domain('LIFECYCLE', [], not_applicable=True),
        'lineage': _domain('LINEAGE', lineage_rules),
    }
    status = 'PASS' if all(x.get('status') in {'PASS', 'NOT_APPLICABLE'} for x in domains.values()) else 'FAIL'
    failures = [r for d in domains.values() for r in d.get('rules', []) if r.get('status') == 'FAIL' and r.get('severity') == 'ERROR']
    scores = [float(d.get('score', 100)) for d in domains.values() if d.get('status') != 'NOT_APPLICABLE']
    explicit_entry_policy = entry_policy is not None
    if explicit_entry_policy:
        entry_execution = _entry_execution_readiness(
            direction=direction_value,
            reference_price=ref,
            entry_policy=entry_policy,
            targets=target_values,
            geometry_context=geometry_context,
        )
    else:
        # Compatibility for direct library callers. Runtime management always
        # supplies the source plan's explicit entry policy in M68.2.1, and the
        # handoff gate below requires an explicit READY_NOW disposition.
        entry_execution = {
            'disposition': 'LEGACY_ENTRY_POLICY_UNSPECIFIED',
            'trade_builder_ready': True,
            'reason_codes': ['RUNTIME_RECERTIFICATION_REQUIRED'],
        }
    trade_builder_ready = bool(
        status == 'PASS'
        and entry_execution.get('trade_builder_ready') is True
    )
    return {
        'certification_id': f"TPC-IO-{final_fp[:16].upper()}",
        'version': CERTIFICATION_VERSION,
        'certification_scope': 'INSTITUTIONAL_OPTIONS_FINAL_PLAN',
        'status': status,
        'certified_at': datetime.now(timezone.utc).isoformat(),
        'reference_market': reference,
        'direction': direction_value,
        'quality_score': round(sum(scores) / len(scores), 2) if scores else 0.0,
        'publishable': status == 'PASS',
        'trade_builder_ready': trade_builder_ready,
        'execution_disposition': entry_execution.get('disposition'),
        'entry_execution': entry_execution,
        'source_certification_id': base.get('certification_id'),
        'source_plan_fingerprint': source_fp,
        'underlying_plan_fingerprint': final_underlying_fp,
        'plan_fingerprint': final_fp,
        'plan_mutated': mutated,
        'lineage_status': 'MUTATED_RECERTIFIED' if mutated else 'UNCHANGED_RECERTIFIED',
        'domains': domains,
        'failure_codes': [x['code'] for x in failures],
        'failure_reasons': [x['message'] for x in failures],
        'strategy': str(strategy or '').upper(),
    }


def certify_option_trade_plan(*, strategy: str, legs: Iterable[dict], stock_certification: dict | None, checks: dict | None, dynamic_management: dict | None) -> dict:
    legs = [dict(x) for x in legs]
    base = dict(stock_certification or {})
    inherited_pass = base.get('status') == 'PASS'
    entry_ready = bool(
        base.get('trade_builder_ready') is True
        and base.get('execution_disposition') == 'READY_NOW'
    )
    strategy_domain = _domain('STRATEGY', _strategy_rules(strategy, legs))
    check_map = dict(checks or {})
    exec_rules = [
        _rule('TPC-EXEC-001', bool(check_map.get('risk_within_budget')), 'Trade risk must be within the governed budget.'),
        _rule('TPC-EXEC-002', bool(check_map.get('defined_risk')), 'Trade must have defined risk.'),
        _rule('TPC-EXEC-003', all(bool(str(x.get('option_symbol') or '').strip()) for x in legs), 'Exact executable option contract identity must be present.'),
        _rule('TPC-EXEC-004', entry_ready, 'Underlying entry must be actionable now under the certified entry/chase/target-room policy.', evidence={'execution_disposition': base.get('execution_disposition'), 'entry_execution': base.get('entry_execution')}),
    ]
    dm = dict(dynamic_management or {})
    mgmt_rules = [
        _rule('TPC-MGMT-010', _f(dm.get('underlying_stop')) is not None, 'Execution handoff must contain the structural stop.'),
        _rule('TPC-MGMT-011', bool(dm.get('underlying_targets')), 'Execution handoff must contain governed underlying targets.'),
        _rule('TPC-MGMT-012', bool(dm.get('trailing_policy')), 'Execution handoff must contain trailing policy.'),
        _rule('TPC-MGMT-013', bool(dm.get('volatility_exit_rule')), 'Execution handoff must contain volatility exit governance.'),
    ]
    lineage_rules = [
        _rule('TPC-LIN-010', inherited_pass, 'Trade Builder certification requires a PASS upstream certification.', evidence={'upstream_scope': base.get('certification_scope'), 'upstream_status': base.get('status')}),
        _rule('TPC-LIN-011', bool(base.get('plan_fingerprint')), 'Final Institutional Options plan fingerprint must be present at Trade Builder handoff.', evidence={'upstream_plan_fingerprint': base.get('plan_fingerprint')}),
    ]
    domains = dict(base.get('domains') or {})
    domains['strategy'] = strategy_domain
    domains['execution'] = _domain('EXECUTION', exec_rules)
    domains['management'] = _domain('AUTONOMOUS_MANAGEMENT', mgmt_rules)
    domains['lineage'] = _domain('LINEAGE', lineage_rules)
    status = 'PASS' if inherited_pass and all(x.get('status') in {'PASS', 'NOT_APPLICABLE'} for x in domains.values()) else 'FAIL'
    failures = [r for d in domains.values() for r in d.get('rules', []) if r.get('status') == 'FAIL' and r.get('severity') == 'ERROR']
    scores = [float(d.get('score', 100)) for d in domains.values() if d.get('status') != 'NOT_APPLICABLE']
    risk_payload = {
        'risk_within_budget': bool(check_map.get('risk_within_budget')),
        'defined_risk': bool(check_map.get('defined_risk')),
    }
    final_fp = plan_fingerprint(
        direction=base.get('direction'), reference_market=base.get('reference_market'),
        entry_zone_low=dm.get('underlying_entry_zone_low'), entry_zone_high=dm.get('underlying_entry_zone_high'),
        structural_stop=dm.get('underlying_stop'), targets=dm.get('underlying_targets') or [],
        strategy=strategy, legs=legs, dynamic_management=dm, risk=risk_payload,
    )
    result = {
        **base,
        'certification_id': f"TPC-TB-{final_fp[:16].upper()}",
        'version': CERTIFICATION_VERSION,
        'certification_scope': 'TRADE_BUILDER_FINAL_PLAN',
        'status': status,
        'certified_at': datetime.now(timezone.utc).isoformat(),
        'quality_score': round(sum(scores) / len(scores), 2) if scores else 0.0,
        'publishable': status == 'PASS',
        'trade_builder_ready': status == 'PASS' and entry_ready,
        'parent_certification_id': base.get('certification_id'),
        'source_plan_fingerprint': base.get('plan_fingerprint'),
        'plan_fingerprint': final_fp,
        'plan_mutated': final_fp != str(base.get('plan_fingerprint') or ''),
        'lineage_status': 'HANDOFF_RECERTIFIED',
        'domains': domains,
        'failure_codes': [x['code'] for x in failures],
        'failure_reasons': [x['message'] for x in failures],
        'strategy': str(strategy or '').upper(),
    }
    return result
