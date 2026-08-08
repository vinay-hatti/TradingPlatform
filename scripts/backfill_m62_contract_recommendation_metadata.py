from __future__ import annotations

from trading_ai.database.session import SessionLocal
from trading_ai.institutional_options.models import ContractRecommendationModel, StrategyCandidateModel


def number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def scorecard(legs: list[dict]) -> dict[str, float]:
    if not legs:
        return {
            "liquidity": 0.0,
            "spread_quality": 0.0,
            "greeks_quality": 0.0,
            "iv_quality": 0.0,
            "execution_quality": 0.0,
            "overall_contract_score": 0.0,
        }
    spread_parts = []
    depth_parts = []
    greek_parts = []
    iv_parts = []
    for leg in legs:
        bid = max(0.0, number(leg.get("bid")))
        ask = max(0.0, number(leg.get("ask")))
        last = max(0.0, number(leg.get("last")))
        midpoint = (bid + ask) / 2.0 if ask > 0 and ask >= bid else last
        spread_pct = (ask - bid) / midpoint if midpoint > 0 and ask >= bid else 1.0
        spread_parts.append(max(0.0, 100.0 * (1.0 - min(spread_pct, 1.0))))
        depth_parts.append(min(100.0, number(leg.get("open_interest")) / 10.0 + number(leg.get("volume")) / 5.0))
        greek_parts.append(max(0.0, 100.0 - abs(abs(number(leg.get("delta"))) - 0.40) * 100.0))
        iv_parts.append(max(0.0, min(100.0, 100.0 - abs(number(leg.get("implied_volatility")) - 0.35) * 100.0)))
    spread_quality = sum(spread_parts) / len(spread_parts)
    depth_quality = sum(depth_parts) / len(depth_parts)
    liquidity = 0.6 * spread_quality + 0.4 * depth_quality
    greeks_quality = sum(greek_parts) / len(greek_parts)
    iv_quality = sum(iv_parts) / len(iv_parts)
    execution_quality = 0.7 * spread_quality + 0.3 * depth_quality
    overall = 0.35 * liquidity + 0.20 * spread_quality + 0.15 * greeks_quality + 0.10 * iv_quality + 0.20 * execution_quality
    return {
        "liquidity": round(liquidity, 2),
        "spread_quality": round(spread_quality, 2),
        "greeks_quality": round(greeks_quality, 2),
        "iv_quality": round(iv_quality, 2),
        "execution_quality": round(execution_quality, 2),
        "overall_contract_score": round(overall, 2),
    }


def main() -> None:
    with SessionLocal() as session:
        strategies = {
            row.strategy_candidate_id: row.strategy
            for row in session.query(StrategyCandidateModel).all()
        }
        rows = session.query(ContractRecommendationModel).all()
        updated = 0
        for row in rows:
            payload = dict(row.payload_json or {})
            changed = False
            strategy = payload.get("strategy") or strategies.get(row.strategy_candidate_id)
            if strategy and payload.get("strategy") != strategy:
                payload["strategy"] = strategy
                changed = True
            if not row.executable and not payload.get("rejection_reasons"):
                reasons = list(payload.get("validation_reasons") or [])
                payload["rejection_reasons"] = reasons
                changed = True
            if not payload.get("optimization_scores"):
                payload["optimization_scores"] = scorecard(list(payload.get("legs") or []))
                changed = True
            if changed:
                row.payload_json = payload
                updated += 1
        session.commit()
        print(f"Milestone 62 contract recommendation metadata backfill: scanned={len(rows)}, updated={updated}")


if __name__ == "__main__":
    main()
