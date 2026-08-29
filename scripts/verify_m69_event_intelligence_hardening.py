from __future__ import annotations
import csv, json
from pathlib import Path
from sqlalchemy import text
from trading_ai.database.session import SessionLocal

symbols = set()
universe = Path('data/universe/us_listed_equities_etfs.csv')
if universe.is_file():
    with universe.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        key = next((name for name in (reader.fieldnames or []) if name.strip().lower() == 'symbol'), None)
        symbols = {str(row.get(key, '')).strip().upper() for row in reader if key}

with SessionLocal() as session:
    date_expr = "CASE WHEN event_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' THEN SUBSTRING(event_date FROM 1 FOR 10)::date ELSE NULL END"
    rows = session.execute(text(f"""
        SELECT symbol,forecast_move_pct,implied_move_pct,historical_move_pct,evidence_json
        FROM institutional_option_valuation_events
        WHERE status='ACTIVE' AND ({date_expr})>=CURRENT_DATE
    """)).mappings().all()
    eligible = [row for row in rows if str(row['symbol']).upper() in symbols or str(row['symbol']).upper() in ('*', 'ALL')]
    coverage = {
        'current_active': len(rows),
        'forecast_eligible': len(eligible),
        'forecast_covered': sum(row['forecast_move_pct'] is not None for row in eligible),
        'implied': sum(row['implied_move_pct'] is not None for row in rows),
        'historical': sum(row['historical_move_pct'] is not None for row in rows),
    }
    coverage['forecast_coverage_pct'] = round(100 * coverage['forecast_covered'] / max(1, coverage['forecast_eligible']), 2)
    methods, outliers = {}, 0
    for row in rows:
        implied = ((row['evidence_json'] or {}).get('institutional_event_intelligence') or {}).get('implied') or {}
        method = implied.get('method') or 'NONE'
        methods[method] = methods.get(method, 0) + 1
        outliers += int(implied.get('outlier_status') in ('CAPPED', 'REJECTED'))

    macro_rows = session.execute(text("""
        SELECT calendar_source,event_type,
               COUNT(DISTINCT SUBSTRING(event_date FROM 1 FOR 10)) AS canonical_event_count,
               COUNT(*) AS row_count
        FROM institutional_option_valuation_events
        WHERE calendar_source IN ('FEDERAL_RESERVE','BLS','BEA')
          AND status='COMPLETED'
          AND date_status IS DISTINCT FROM 'INVALIDATED'
        GROUP BY calendar_source,event_type
        ORDER BY calendar_source,event_type
    """)).mappings().all()
    macro_history = {row['event_type']: int(row['canonical_event_count']) for row in macro_rows}
    macro_detail = [dict(row) for row in macro_rows]
    duplicate_groups = session.execute(text("""
        SELECT COUNT(*) FROM (
            SELECT calendar_source,event_type,SUBSTRING(event_date FROM 1 FOR 10)
            FROM institutional_option_valuation_events
            WHERE calendar_source IN ('FEDERAL_RESERVE','BLS','BEA')
              AND status IN ('ACTIVE','COMPLETED')
              AND date_status IS DISTINCT FROM 'INVALIDATED'
            GROUP BY calendar_source,event_type,SUBSTRING(event_date FROM 1 FOR 10)
            HAVING COUNT(*)>1
        ) duplicates
    """)).scalar()
    stale = session.execute(text(f"SELECT COUNT(*) FROM institutional_option_valuation_events WHERE status='ACTIVE' AND ({date_expr})<CURRENT_DATE")).scalar()
    completed_fomc = macro_history.get('FOMC', 0)
    future_fomc = session.execute(text(f"""
        SELECT COUNT(DISTINCT SUBSTRING(event_date FROM 1 FOR 10))
        FROM institutional_option_valuation_events
        WHERE calendar_source='FEDERAL_RESERVE' AND event_type='FOMC'
          AND status='ACTIVE' AND date_status IS DISTINCT FROM 'INVALIDATED'
          AND ({date_expr})>=CURRENT_DATE
    """)).scalar()
    unscheduled_fomc = session.execute(text("""
        SELECT COUNT(*) FROM institutional_option_valuation_events
        WHERE calendar_source='FEDERAL_RESERVE' AND event_type='FOMC'
          AND status='COMPLETED' AND date_status IS DISTINCT FROM 'INVALIDATED'
          AND event_components_json::text ILIKE '%UNSCHEDULED_MEETING%'
    """)).scalar()
    result = {
        'coverage': coverage,
        'implied_methods': methods,
        'governed_outliers': outliers,
        'macro_history': macro_history,
        'macro_history_detail': macro_detail,
        'fomc_detail': {
            'completed_historical': int(completed_fomc or 0),
            'future_scheduled': int(future_fomc or 0),
            'unscheduled_historical': int(unscheduled_fomc or 0),
        },
        'duplicate_macro_groups': int(duplicate_groups or 0),
        'elapsed_active_events': int(stale or 0),
        'acceptance': {
            'forecast_coverage_ge_90': coverage['forecast_coverage_pct'] >= 90,
            'legacy_iv_floor_current': methods.get('ATM_STRADDLE_WITH_TERM_VARIANCE_FLOOR', 0),
            'elapsed_active_zero': stale == 0,
            'fomc_completed_plausible': 75 <= completed_fomc <= 100,
            'fomc_future_present': int(future_fomc or 0) > 0,
            'fomc_plausible': 75 <= completed_fomc <= 100 and int(future_fomc or 0) > 0,
            'bea_history_present': macro_history.get('GDP', 0) > 20 and macro_history.get('PERSONAL_INCOME_AND_OUTLAYS', 0) > 50,
            'duplicate_macro_events_zero': int(duplicate_groups or 0) == 0,
        },
    }
    print(json.dumps(result, indent=2, default=str))
