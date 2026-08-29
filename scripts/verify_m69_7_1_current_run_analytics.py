from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def static_checks() -> dict[str, bool]:
    service = (ROOT / "src/trading_ai/analytics_dashboard/service.py").read_text()
    migration = (ROOT / "migrations/versions/m69_008_current_valuation_run_lookup.py").read_text()
    test = (ROOT / "tests/milestone69/test_m69_7_1_current_run_analytics.py").read_text()
    where_token = 'OptionValuationSnapshotModel.payload_json["valuation_run_id"].as_string()'
    return {
        "database_current_run_filter": where_token in service,
        "filter_precedes_order_and_limit": (
            "current_valuation_snapshot_query" in service
            and ").limit(limit)" in service
            and "max(limit * 4, limit)" not in service
        ),
        "python_post_limit_filter_removed": (
            "rows = [row for row in rows if (row.payload_json or {}).get('valuation_run_id')"
            not in service
        ),
        "current_run_lookup_index": (
            "ix_m69_snapshot_valuation_run_id" in migration
            and "payload_json ->> 'valuation_run_id'" in migration
        ),
        "historical_high_edge_regression": (
            "Historical rows deliberately outrank every current row" in test
            and "Counter(expected)" in test
        ),
        "bound_json_key_regression_contract": (
            'assert "valuation_run_id" in parameter_values' in test
            and 'assert "M69-RUN-CURRENT" in parameter_values' in test
            and "assert statement.whereclause is not None" in test
        ),
    }


def runtime_checks() -> dict[str, bool]:
    from sqlalchemy import select

    from trading_ai.analytics_dashboard.service import AnalyticsDashboardService
    from trading_ai.database.session import SessionLocal
    from trading_ai.option_valuation_intelligence.models import OptionValuationPublicationModel

    dashboard = AnalyticsDashboardService(SessionLocal).mispricing(limit=10_000)
    with SessionLocal() as session:
        publication = session.execute(
            select(OptionValuationPublicationModel).where(
                OptionValuationPublicationModel.publication_name
                == "current_option_valuation_intelligence"
            )
        ).scalars().first()

    authoritative = dict(publication.payload_json or {}) if publication else {}
    summary = dict(dashboard.get("summary") or {})
    candidates = list(dashboard.get("candidates") or [])
    classifications = [str(item.get("classification")) for item in candidates]
    api_counts = {
        "underpriced": sum("UNDERPRICED" in value for value in classifications),
        "overpriced": sum("OVERPRICED" in value for value in classifications),
        "fair_value": sum(value == "FAIR_VALUE" for value in classifications),
    }
    return {
        "runtime_publication_exists": bool(publication),
        "runtime_api_candidate_count_matches": (
            len(candidates) == int(authoritative.get("built") or 0)
            and summary.get("contracts_valued") == int(authoritative.get("built") or 0)
        ),
        "runtime_underpriced_count_matches": (
            api_counts["underpriced"] == int(authoritative.get("underpriced") or 0)
            and summary.get("underpriced") == int(authoritative.get("underpriced") or 0)
        ),
        "runtime_overpriced_count_matches": (
            api_counts["overpriced"] == int(authoritative.get("overpriced") or 0)
            and summary.get("overpriced") == int(authoritative.get("overpriced") or 0)
        ),
        "runtime_fair_value_count_matches": (
            api_counts["fair_value"] == int(authoritative.get("fair_value") or 0)
            and summary.get("fair_value") == int(authoritative.get("fair_value") or 0)
        ),
        "runtime_average_edge_matches": abs(
            float(summary.get("average_edge_score") or 0.0)
            - float(authoritative.get("average_edge_score") or 0.0)
        ) < 0.0001,
        "runtime_all_classifications_visible": all(
            int((authoritative.get("classification_counts") or {}).get(name) or 0) == 0
            or name in classifications
            for name in (
                "STRONG_UNDERPRICED",
                "MODERATELY_UNDERPRICED",
                "FAIR_VALUE",
                "MODERATELY_OVERPRICED",
                "STRONG_OVERPRICED",
            )
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", action="store_true")
    args = parser.parse_args()
    checks = static_checks()
    if args.runtime:
        checks |= runtime_checks()
    result = {
        "version": "M69.7.2-CURRENT-RUN-ANALYTICS-VERIFICATION-1.0",
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
