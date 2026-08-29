from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def static_checks() -> dict[str, bool]:
    service = (ROOT / "src/trading_ai/option_valuation_intelligence/service.py").read_text()
    engine = (ROOT / "src/trading_ai/option_valuation_intelligence/engine.py").read_text()
    dashboard = (ROOT / "src/trading_ai/analytics_dashboard/service.py").read_text()
    persistence = (ROOT / "src/trading_ai/scanner/options_market_data_ingestion/persistence.py").read_text()
    mapper = (ROOT / "src/trading_ai/scanner/options_market_data_ingestion/polygon_snapshot_provider.py").read_text()
    migration = (ROOT / "migrations/versions/m69_007_coherent_option_valuation_inputs.py").read_text()
    return {
        "coherent_input_resolver": "load_coherent_market_inputs" in service,
        "historical_lineage_deduplicated": "latest_by_lineage" in service,
        "invalid_inputs_fail_closed": "excluded_market_input_reasons" in service,
        "decision_exact_lineage": all(
            token in service for token in (
                "InstitutionalDecisionSnapshotModel.strategy_candidate_id == row.strategy_candidate_id",
                "InstitutionalDecisionSnapshotModel.contract_recommendation_id == row.contract_recommendation_id",
            )
        ),
        "one_sided_distribution_gate": "distribution_anomaly" in service,
        "per_leg_dte": "leg_dtes[leg_index]" in engine and "per_leg_dte" in engine,
        "dashboard_exact_strategy_lineage": "valuation_by_lineage" in dashboard and "strategy_by_id" in dashboard,
        "dashboard_current_actionability": "payload.get('valuation_actionable', False)" in dashboard,
        "provider_quote_timestamp_persisted": "quote_timestamp" in mapper and "quote_timestamp" in persistence,
        "schema_provenance": "quote_timestamp" in migration and "source_underlying_price" in migration,
    }


def psx_regression_checks() -> dict[str, bool]:
    from trading_ai.option_valuation_intelligence.engine import InstitutionalOptionValuationEngine
    from trading_ai.option_valuation_intelligence.market_inputs import resolve_coherent_market_inputs

    contract = {
        "strategy": "BULL_CALL_SPREAD",
        "legs": [
            {"side": "BUY", "option_type": "CALL", "option_symbol": "PSX200", "expiry": "2026-09-18", "strike": 200},
            {"side": "SELL", "option_type": "CALL", "option_symbol": "PSX220", "expiry": "2026-09-18", "strike": 220},
        ],
    }

    def quote(symbol, quote_date, bid, ask, iv):
        return {
            "option_symbol": symbol, "quote_date": quote_date, "expiry": date(2026, 9, 18),
            "bid": bid, "ask": ask, "last": (bid + ask) / 2, "implied_volatility": iv,
        }

    coherent = resolve_coherent_market_inputs(
        contract=contract,
        option_rows=[
            quote("PSX200", date(2026, 8, 14), 31.0, 34.0, .2691),
            quote("PSX220", date(2026, 8, 14), 15.5, 18.6, .3107),
            quote("PSX200", date(2026, 8, 15), 31.8, 34.9, .29),
            quote("PSX220", date(2026, 8, 15), 15.5, 18.6, .293),
        ],
        price_rows=[
            {"date": date(2026, 8, 5), "close": 202.55},
            {"date": date(2026, 8, 14), "close": 233.61},
        ],
    )
    result = InstitutionalOptionValuationEngine().evaluate(
        opportunity={"direction": "BULLISH"}, contract=coherent.payload
    )
    return {
        "psx_current_market_date": coherent.market_date == date(2026, 8, 14),
        "psx_correct_dte": coherent.dte_min == coherent.dte_max == 35,
        "psx_current_package_mid": abs(float(result["market_mid"]) - 15.45) < 1e-9,
        "psx_stale_7_10_removed": abs(float(result["market_mid"]) - 7.10) > 1.0,
        "psx_not_clipped_100": abs(float(result["mispricing_pct"])) < 100.0,
    }


def runtime_checks() -> dict[str, bool]:
    from sqlalchemy import select

    from trading_ai.database.session import SessionLocal
    from trading_ai.option_valuation_intelligence.models import (
        OptionValuationPublicationModel,
        OptionValuationSnapshotModel,
    )

    with SessionLocal() as session:
        publication = session.execute(
            select(OptionValuationPublicationModel).where(
                OptionValuationPublicationModel.publication_name
                == "current_option_valuation_intelligence"
            )
        ).scalars().first()
        payload = dict(publication.payload_json or {}) if publication else {}
        run_id = payload.get("valuation_run_id")
        rows = session.execute(select(OptionValuationSnapshotModel)).scalars().all()
        current = [row for row in rows if (row.payload_json or {}).get("valuation_run_id") == run_id]
        snapshots = [dict(row.payload_json or {}) for row in current]
        return {
            "runtime_publication_exists": bool(publication and run_id),
            "runtime_publication_not_failed": bool(publication and publication.status in {"READY", "DEGRADED"}),
            "runtime_current_snapshots_exist": bool(current),
            "runtime_all_inputs_coherent": bool(snapshots) and all(
                item.get("market_input_status") == "CURRENT_COHERENT"
                and item.get("market_input_as_of")
                and item.get("quote_input_snapshot_id")
                for item in snapshots
            ),
            "runtime_no_zero_dte": bool(snapshots) and all(float(item.get("dte") or 0) > 0 for item in snapshots),
            "runtime_no_distribution_anomaly": not bool(
                (payload.get("diagnostics") or {}).get("distribution_anomaly")
            ),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", action="store_true")
    args = parser.parse_args()
    checks = static_checks() | psx_regression_checks()
    if args.runtime:
        checks |= runtime_checks()
    result = {
        "version": "M69.7-COHERENT-OPTION-VALUATION-VERIFICATION-1.0",
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
