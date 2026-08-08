from __future__ import annotations

from hashlib import sha256
from math import erf, exp, isfinite, log, sqrt
from statistics import mean, median, pstdev
from typing import Any


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, float(v)))


def num(v, default=0.0):
    try:
        value = float(v)
        return value if isfinite(value) else default
    except (TypeError, ValueError):
        return default


def deep_get(d: Any, *keys, default=None):
    if isinstance(d, dict):
        lowered = {str(k).lower(): v for k, v in d.items()}
        for key in keys:
            if key.lower() in lowered:
                return lowered[key.lower()]
        for value in d.values():
            result = deep_get(value, *keys, default=None)
            if result is not None:
                return result
    elif isinstance(d, (list, tuple)):
        for value in d:
            result = deep_get(value, *keys, default=None)
            if result is not None:
                return result
    return default


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def bs_price(s: float, k: float, t: float, r: float, sigma: float, right: str, dividend_yield: float = 0.0) -> float:
    if s <= 0 or k <= 0 or t <= 0 or sigma <= 0:
        return max(0.0, s-k) if right == 'C' else max(0.0, k-s)
    d1 = (log(s/k) + (r-dividend_yield + 0.5*sigma*sigma)*t)/(sigma*sqrt(t))
    d2 = d1-sigma*sqrt(t)
    if right == 'C':
        return s*exp(-dividend_yield*t)*norm_cdf(d1)-k*exp(-r*t)*norm_cdf(d2)
    return k*exp(-r*t)*norm_cdf(-d2)-s*exp(-dividend_yield*t)*norm_cdf(-d1)


def extract_legs(contract: dict) -> list[dict]:
    legs = contract.get('legs') if isinstance(contract, dict) else None
    if isinstance(legs, list) and legs:
        return [x for x in legs if isinstance(x, dict)]
    return [contract] if isinstance(contract, dict) else []


def leg_side_sign(leg: dict) -> float:
    return -1.0 if str(leg.get('side', 'BUY')).upper() in {'SELL', 'SHORT'} else 1.0


def leg_market_price(leg: dict) -> tuple[float, float, float]:
    bid = num(deep_get(leg, 'bid', 'bid_price'))
    ask = num(deep_get(leg, 'ask', 'ask_price'))
    last = num(deep_get(leg, 'last', 'last_price', 'mark', 'mid', 'option_mark', 'price'))
    if bid > 0 and ask > 0:
        mid = (bid + ask) / 2.0
    else:
        mid = last if last > 0 else max(bid, ask, 0.0)
    return bid, ask, mid


def weighted_leg_value(legs: list[dict], *keys: str) -> tuple[float | None, int]:
    values: list[tuple[float, float]] = []
    for leg in legs:
        raw = deep_get(leg, *keys)
        value = num(raw)
        if raw is not None and value > 0:
            qty = max(1.0, abs(num(deep_get(leg, 'quantity_ratio', 'ratio', 'quantity'), 1.0)))
            values.append((value, qty))
    if not values:
        return None, 0
    total_weight = sum(weight for _, weight in values)
    return sum(value * weight for value, weight in values) / total_weight, len(values)


class InstitutionalOptionValuationEngine:
    POLICY = 'M69-OPTION-VALUATION-1.2'
    MODERATE_THRESHOLD_PCT = 4.0
    STRONG_THRESHOLD_PCT = 12.0

    def evaluate(self, *, opportunity: dict, contract: dict, inflection: dict | None = None,
                 siblings: list[dict] | None = None) -> dict:
        inflection = inflection or {}
        siblings = siblings or []
        legs = extract_legs(contract)
        priced_legs = []
        for leg in legs:
            lbid, lask, lmid = leg_market_price(leg)
            qty = max(1.0, abs(num(deep_get(leg, 'quantity_ratio', 'ratio', 'quantity'), 1.0)))
            sign = leg_side_sign(leg)
            priced_legs.append({'leg': leg, 'bid': lbid, 'ask': lask, 'mid': lmid, 'qty': qty, 'sign': sign})

        # Natural package prices preserve debit/credit sign. For a credit package both values may be negative.
        quoted = [x for x in priced_legs if x['bid'] > 0 and x['ask'] >= x['bid']]
        if quoted and len(quoted) == len(priced_legs):
            buy_natural = sum(x['qty'] * (x['ask'] if x['sign'] > 0 else -x['bid']) for x in priced_legs)
            sell_natural = sum(x['qty'] * (x['bid'] if x['sign'] > 0 else -x['ask']) for x in priced_legs)
            mid = (buy_natural + sell_natural) / 2.0
            package_spread = max(0.0, buy_natural - sell_natural)
        else:
            buy_natural = sell_natural = None
            mid = sum(x['sign'] * x['mid'] * x['qty'] for x in priced_legs)
            package_spread = 0.0

        if abs(mid) < 0.000001:
            net_dc = num(deep_get(contract, 'net_debit_credit', 'net_debit', 'net_credit'))
            mid = net_dc if abs(net_dc) > 0 else 0.0

        gross_leg_premium = sum(abs(x['mid']) * x['qty'] for x in priced_legs)
        # A robust reference avoids exploding percentages for near-zero-cost or near-zero-credit structures.
        reference_value = max(abs(mid), gross_leg_premium * 0.20, 0.25)
        low_net_premium = abs(mid) < max(0.05, gross_leg_premium * 0.05)

        s = num(deep_get(contract, 'underlying_price', 'spot', 'underlying_last'),
                num(deep_get(opportunity, 'underlying_price', 'spot_price', 'current_price', 'last_price', 'price')))
        k = num(deep_get(contract, 'strike', 'strike_price'), s)

        leg_iv, iv_count = weighted_leg_value(legs, 'implied_volatility', 'iv')
        leg_rv, rv_count = weighted_leg_value(legs, 'realized_volatility_20d', 'realized_volatility', 'rv')
        leg_forecast, forecast_count = weighted_leg_value(legs, 'forecast_volatility', 'expected_realized_volatility', 'forward_volatility')
        iv_raw = leg_iv if leg_iv is not None else deep_get(contract, 'implied_volatility', 'iv')
        rv_raw = leg_rv if leg_rv is not None else deep_get(contract, 'realized_volatility_20d', 'realized_volatility', 'rv')
        forecast_raw = leg_forecast if leg_forecast is not None else deep_get(contract, 'forecast_volatility', 'expected_realized_volatility', 'forward_volatility')
        iv = max(0.01, num(iv_raw, 0.30))
        rv_available = rv_raw is not None and num(rv_raw) > 0
        rv = max(0.01, num(rv_raw, iv))
        forecast_available = forecast_raw is not None and num(forecast_raw) > 0
        forecast_input = max(0.01, num(forecast_raw, rv if rv_available else iv))

        dte = max(1, num(deep_get(contract, 'dte', 'days_to_expiration'), 45))
        right = str(deep_get(contract, 'right', 'option_type', default='C')).upper()[:1]
        risk_free = num(deep_get(contract, 'risk_free_rate'), 0.04)
        dividend_yield = max(0.0, num(deep_get(contract, 'dividend_yield'), 0.0))

        inf_score = num(inflection.get('inflection_score'), 50)
        inf_dir = str(inflection.get('direction', 'NEUTRAL')).upper()
        opp_dir = str(opportunity.get('direction', 'NEUTRAL')).upper()
        aligned = ((opp_dir.startswith('BULL') and inf_dir.startswith('BULL')) or
                   (opp_dir.startswith('BEAR') and inf_dir.startswith('BEAR')))
        dealer_score_raw = deep_get(opportunity, 'dealer_score', 'dealer_context_score', 'institutional_positioning_score')
        dealer_available = dealer_score_raw is not None
        dealer = clamp(num(dealer_score_raw, 50))
        event_score_raw = deep_get(opportunity, 'event_pricing_score', 'event_score')
        event_available = event_score_raw is not None
        event_score = clamp(num(event_score_raw, 50))
        peer_iv_raw = deep_get(opportunity, 'peer_implied_volatility', 'sector_implied_volatility', 'relative_value_iv')
        relative_available = peer_iv_raw is not None and num(peer_iv_raw) > 0
        peer_iv = max(0.01, num(peer_iv_raw, iv))

        quoted_spreads = []
        for item in quoted:
            if item['mid'] > 0:
                quoted_spreads.append((item['ask']-item['bid'])/item['mid']*100)
        spread_pct = mean(quoted_spreads) if quoted_spreads else 25.0
        persisted_liquidity = num(deep_get(contract, 'liquidity_score'), 50)
        liquidity = clamp(100-spread_pct*1.5 + persisted_liquidity*0.20)

        sibling_ivs = []
        for sibling in siblings:
            sibling_value, _ = weighted_leg_value(extract_legs(sibling), 'implied_volatility', 'iv')
            if sibling_value is None:
                sibling_value = num(deep_get(sibling, 'implied_volatility', 'iv'))
            if sibling_value and sibling_value > 0:
                sibling_ivs.append(sibling_value)
        surface_available = len(sibling_ivs) >= 2
        local_surface_iv = median(sibling_ivs) if surface_available else iv
        surface_iv_gap = local_surface_iv-iv
        surface_score = clamp(50 + surface_iv_gap*200)

        base_forecast = 0.50*forecast_input + 0.30*rv + 0.20*local_surface_iv
        inflection_vol_adjust = ((inf_score-50)/50) * (0.08 if aligned else -0.03)
        dealer_vol_adjust = ((dealer-50)/50) * 0.035
        event_vol_adjust = ((event_score-50)/50) * 0.08 if event_available else 0.0
        relative_vol_adjust = ((peer_iv-iv)/max(iv, 0.01))*0.10 if relative_available else 0.0
        forecast_sigma = max(0.05, min(2.50, base_forecast*(1+inflection_vol_adjust+dealer_vol_adjust+event_vol_adjust+relative_vol_adjust)))

        if s > 0 and priced_legs:
            market_theoretical = 0.0
            model_fair_value = 0.0
            for item in priced_legs:
                leg = item['leg']
                lk = num(deep_get(leg, 'strike', 'strike_price'), k)
                lright = str(deep_get(leg, 'right', 'option_type', default=right)).upper()[:1]
                liv = max(0.01, num(deep_get(leg, 'implied_volatility', 'iv'), iv))
                leg_forecast_sigma = max(0.05, min(2.50, liv * (forecast_sigma / max(iv, 0.01))))
                market_theoretical += item['sign'] * item['qty'] * bs_price(s, lk, dte/365.0, risk_free, liv, lright, dividend_yield)
                model_fair_value += item['sign'] * item['qty'] * bs_price(s, lk, dte/365.0, risk_free, leg_forecast_sigma, lright, dividend_yield)
            valuation_basis = 'INDEPENDENT_MODEL'
        else:
            market_theoretical = mid
            model_fair_value = mid
            valuation_basis = 'MARKET_FALLBACK'

        gross_edge_value = model_fair_value-mid
        gross_edge_pct = gross_edge_value/reference_value*100

        if package_spread > 0:
            fill_fraction = 0.20 + 0.30 * (1.0 - liquidity/100.0)
            expected_slippage = min((package_spread/2.0) * fill_fraction, reference_value*0.08)
        else:
            expected_slippage = reference_value*0.03
        liquidity_penalty_value = max(0.0, expected_slippage)
        executable_fair_value = model_fair_value-liquidity_penalty_value
        raw_executable_edge_pct = (executable_fair_value-mid)/max(abs(mid), 0.01)*100
        executable_edge_pct = (executable_fair_value-mid)/reference_value*100
        analytical_edge_pct = max(-100.0, min(100.0, executable_edge_pct))

        components = {
            'model_valuation_edge_pct': round((model_fair_value-market_theoretical)/reference_value*100, 4),
            'volatility_edge_pct': round((forecast_sigma-iv)/max(iv, 0.01)*10, 4),
            'surface_edge_pct': round(surface_iv_gap/max(iv, 0.01)*5, 4),
            'relative_value_edge_pct': round((peer_iv-iv)/max(iv, 0.01)*5, 4) if relative_available else 0.0,
            'event_edge_pct': round((event_score-50)/10, 4) if event_available else 0.0,
            'dealer_flow_edge_pct': round((dealer-50)/10, 4) if dealer_available else 0.0,
            'inflection_edge_pct': round((inf_score-50)/10*(1 if aligned else -0.35), 4),
            'execution_edge_pct': round(-liquidity_penalty_value/reference_value*100, 4),
        }
        coverage = {
            'volatility': {'available': iv_raw is not None and iv > 0, 'quality': 'LEG_WEIGHTED' if iv_count else ('EXACT' if iv_raw is not None else 'FALLBACK')},
            'realized_volatility': {'available': rv_available, 'quality': 'LEG_WEIGHTED' if rv_count else ('EXACT' if rv_available else 'FALLBACK_TO_IV')},
            'forecast_volatility': {'available': forecast_available or rv_available, 'quality': 'LEG_WEIGHTED' if forecast_count else ('EXACT' if forecast_available else ('DERIVED_FROM_RV' if rv_available else 'FALLBACK_TO_IV'))},
            'surface': {'available': surface_available, 'quality': 'LOCAL_NEIGHBORS' if surface_available else 'NEUTRAL_FALLBACK', 'neighbor_count': len(sibling_ivs)},
            'relative_value': {'available': relative_available, 'quality': 'GOVERNED_PEER_CONTEXT' if relative_available else 'NEUTRAL_FALLBACK'},
            'event': {'available': event_available, 'quality': 'GOVERNED_EVENT_CONTEXT' if event_available else 'NO_EVENT_CONTEXT'},
            'dealer_flow': {'available': dealer_available, 'quality': 'GOVERNED_DEALER_CONTEXT' if dealer_available else 'NEUTRAL_FALLBACK'},
            'liquidity': {'available': bool(quoted) and len(quoted) == len(priced_legs), 'quality': 'PACKAGE_NATURAL_SPREAD' if quoted else 'CONSERVATIVE_FALLBACK'},
        }
        exact_domains = sum(1 for v in coverage.values() if v['available'])
        coverage_pct = exact_domains/len(coverage)*100
        nonzero = [abs(v) for v in components.values() if abs(v) > 0.01]
        dispersion = pstdev(nonzero) if len(nonzero) > 1 else 0.0
        stability = clamp(45 + exact_domains*5 + min(15, len(nonzero)*2) - min(25, dispersion*1.5) + liquidity*0.10)
        confidence = clamp(25 + coverage_pct*0.35 + liquidity*0.15 + stability*0.20 + min(15, abs(analytical_edge_pct)))
        edge_score = clamp(50 + analytical_edge_pct*2)

        if analytical_edge_pct >= self.STRONG_THRESHOLD_PCT:
            classification = 'STRONG_UNDERPRICED'
        elif analytical_edge_pct >= self.MODERATE_THRESHOLD_PCT:
            classification = 'MODERATELY_UNDERPRICED'
        elif analytical_edge_pct <= -self.STRONG_THRESHOLD_PCT:
            classification = 'STRONG_OVERPRICED'
        elif analytical_edge_pct <= -self.MODERATE_THRESHOLD_PCT:
            classification = 'MODERATELY_OVERPRICED'
        else:
            classification = 'FAIR_VALUE'

        persistence = 'INTRADAY_TO_1_SESSION' if stability < 55 else ('1_3_SESSIONS' if stability < 75 else '3_10_SESSIONS')
        evidence = [
            f'Model forecast volatility {forecast_sigma:.3f} versus market IV {iv:.3f}',
            f'Model fair value {model_fair_value:.4f} versus package mid {mid:.4f}',
            f'Executable edge {analytical_edge_pct:.2f}% using robust reference {reference_value:.4f}',
            f'Inflection {inf_score:.1f} ({inf_dir}); dealer {dealer:.1f}',
            f'Domain coverage {coverage_pct:.1f}% ({exact_domains}/{len(coverage)})',
        ]
        conflicts = []
        if spread_pct > 20:
            conflicts.append(f'Wide average leg spread {spread_pct:.1f}%')
        if low_net_premium:
            conflicts.append('Near-zero net package premium; robust gross-premium reference applied')
        if not aligned and inf_dir != 'NEUTRAL':
            conflicts.append('Inflection direction conflicts with opportunity')
        missing = [name for name, value in coverage.items() if not value['available']]
        if missing:
            conflicts.append('Neutral fallbacks used for: ' + ', '.join(missing))
        invalidation = [
            'Executable package price converges within 2% of model fair value',
            'Forecast-volatility relationship reverses materially',
            'Underlying transition state materially reverses',
            'Dealer-flow thesis reverses or option liquidity breaches policy',
        ]

        raw = {
            'policy_version': self.POLICY,
            'valuation_basis': valuation_basis,
            'market_mid': round(mid, 6),
            'buy_natural': None if buy_natural is None else round(buy_natural, 6),
            'sell_natural': None if sell_natural is None else round(sell_natural, 6),
            'package_spread': round(package_spread, 6),
            'gross_leg_premium': round(gross_leg_premium, 6),
            'reference_value': round(reference_value, 6),
            'low_net_premium': low_net_premium,
            'market_theoretical_value': round(market_theoretical, 6),
            'model_fair_value': round(model_fair_value, 6),
            'fair_value': round(executable_fair_value, 6),
            'gross_theoretical_edge_pct': round(gross_edge_pct, 4),
            'raw_executable_edge_pct': round(raw_executable_edge_pct, 4),
            'mispricing_pct': round(analytical_edge_pct, 4),
            'edge_score': round(edge_score, 4),
            'confidence': round(confidence, 4),
            'stability_index': round(stability, 4),
            'classification': classification,
            'expected_persistence': persistence,
            'components': components,
            'component_coverage': coverage,
            'component_coverage_pct': round(coverage_pct, 4),
            'volatility': {'market_iv': iv, 'realized_volatility': rv, 'forecast_volatility': round(forecast_sigma, 6), 'iv_rv_spread': iv-rv},
            'surface': {'score': round(surface_score, 4), 'local_surface_iv': round(local_surface_iv, 6), 'neighbor_count': len(sibling_ivs)},
            'relative_value': {'peer_iv': round(peer_iv, 6), 'available': relative_available},
            'event_pricing': {'score': event_score, 'status': coverage['event']['quality']},
            'dealer_flow': {'score': dealer, 'status': coverage['dealer_flow']['quality']},
            'liquidity': {'score': round(liquidity, 4), 'spread_pct': round(spread_pct, 4), 'expected_slippage': round(expected_slippage, 6), 'penalty_pct': round(liquidity_penalty_value/reference_value*100, 4)},
            'thresholds': {'moderate_pct': self.MODERATE_THRESHOLD_PCT, 'strong_pct': self.STRONG_THRESHOLD_PCT},
            'evidence': evidence,
            'conflicting_evidence': conflicts,
            'invalidation': invalidation,
        }
        uncertainty = max(0.03, (100-confidence)/200)
        raw['fair_value_low'] = round(executable_fair_value - abs(executable_fair_value)*uncertainty, 6)
        raw['fair_value_high'] = round(executable_fair_value + abs(executable_fair_value)*uncertainty, 6)
        raw['state_hash'] = sha256(repr(sorted((k, str(v)) for k, v in raw.items() if k != 'state_hash')).encode()).hexdigest()
        return raw
