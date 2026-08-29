from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from sqlalchemy import text
from trading_ai.database.session import SessionLocal
from backfill_m69_historical_macro_events import fed, bea


def _duplicate_losers(session):
    rows = session.execute(text("""
        SELECT event_id,calendar_source,event_type,SUBSTRING(event_date FROM 1 FOR 10) AS event_day,
               status,source_updated_at,revision_number,source_event_key
        FROM institutional_option_valuation_events
        WHERE calendar_source IN ('FEDERAL_RESERVE','BLS','BEA')
          AND status IN ('ACTIVE','COMPLETED')
          AND date_status IS DISTINCT FROM 'INVALIDATED'
        ORDER BY calendar_source,event_type,event_day,
                 CASE WHEN status='ACTIVE' THEN 0 ELSE 1 END,
                 source_updated_at DESC NULLS LAST,revision_number DESC NULLS LAST,event_id
    """)).mappings().all()
    groups = {}
    for row in rows:
        groups.setdefault((row['calendar_source'], row['event_type'], row['event_day']), []).append(row)
    losers = []
    duplicate_groups = 0
    for members in groups.values():
        if len(members) > 1:
            duplicate_groups += 1
            losers.extend(row['event_id'] for row in members[1:])
    return duplicate_groups, losers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start-year', type=int, default=2016)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    today = datetime.now(timezone.utc).date()
    fed_rows = fed(args.start_year)
    valid_completed_fed = {row[3].isoformat() for row in fed_rows if row[3] <= today}
    valid_future_fed = {row[3].isoformat() for row in fed_rows if row[3] > today}
    valid_bea = {(row[1], row[3].isoformat()) for row in bea(args.start_year)}
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        existing_fed = session.execute(text("""
            SELECT event_id,event_date,status FROM institutional_option_valuation_events
            WHERE calendar_source='FEDERAL_RESERVE' AND event_type='FOMC'
              AND SUBSTRING(event_date FROM 1 FOR 4)::int>=:year
              AND status IN ('ACTIVE','COMPLETED')
              AND date_status IS DISTINCT FROM 'INVALIDATED'
        """), {'year': args.start_year}).mappings().all()
        invalid_fed = []
        for row in existing_fed:
            event_day = str(row['event_date'])[:10]
            authoritative = valid_completed_fed if event_day <= today.isoformat() else valid_future_fed
            if event_day not in authoritative:
                invalid_fed.append(row['event_id'])
        bea_rows = session.execute(text("""
            SELECT event_id,event_type,event_date,status FROM institutional_option_valuation_events
            WHERE calendar_source='BEA' AND SUBSTRING(event_date FROM 1 FOR 4)::int>=:year
              AND status IN ('ACTIVE','COMPLETED')
              AND date_status IS DISTINCT FROM 'INVALIDATED'
        """), {'year': args.start_year}).mappings().all()
        invalid_bea = [row['event_id'] for row in bea_rows
                       if (row['event_type'], str(row['event_date'])[:10]) not in valid_bea
                       and str(row['event_date'])[:10] < today.isoformat()]
        duplicate_groups, duplicate_losers = _duplicate_losers(session)
        ids = sorted(set(invalid_fed + invalid_bea + duplicate_losers))
        outcomes = 0
        if args.apply and ids:
            session.execute(text("""
                UPDATE institutional_option_valuation_events
                SET status='SUPERSEDED',date_status='INVALIDATED',
                    calculation_method='MACRO_FOMC_SPLIT_PATH_RECONCILIATION_V3',source_updated_at=:now
                WHERE event_id=ANY(:ids)
            """), {'ids': ids, 'now': now})
            outcomes = session.execute(text("""
                UPDATE institutional_event_outcomes
                SET status='INVALIDATED',finalized_at=:now
                WHERE event_id=ANY(:ids) AND status IS DISTINCT FROM 'INVALIDATED'
            """), {'ids': ids, 'now': now}).rowcount
            session.commit()
        print(json.dumps({
            'status': 'APPLIED' if args.apply else 'DRY_RUN',
            'authoritative_completed_fomc_dates': len(valid_completed_fed),
            'authoritative_future_fomc_dates': len(valid_future_fed),
            'authoritative_bea_releases': len(valid_bea),
            'invalid_fed_events': len(invalid_fed),
            'invalid_bea_events': len(invalid_bea),
            'duplicate_macro_groups': duplicate_groups,
            'duplicate_macro_events_superseded': len(set(duplicate_losers)),
            'outcomes_invalidated': outcomes,
            'sample_event_ids': ids[:20],
        }, indent=2, default=str))


if __name__ == '__main__':
    main()
