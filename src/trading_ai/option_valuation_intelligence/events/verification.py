from __future__ import annotations
from datetime import date, datetime, timezone
from sqlalchemy import func, select
from trading_ai.option_valuation_intelligence.models import OptionValuationEventModel

class EventCalendarVerificationService:
    def __init__(self,session_factory):self.session_factory=session_factory
    def verify(self)->dict:
        with self.session_factory() as s:
            rows=s.execute(select(OptionValuationEventModel).where(OptionValuationEventModel.status=='ACTIVE')).scalars().all()
            dup=s.execute(select(OptionValuationEventModel.calendar_source,OptionValuationEventModel.source_event_key,func.count()).where(OptionValuationEventModel.source_event_key.is_not(None)).group_by(OptionValuationEventModel.calendar_source,OptionValuationEventModel.source_event_key).having(func.count()>1)).all()
        stale=[r.event_id for r in rows if r.event_date < date.today().isoformat()]
        missing_dates=[r.event_id for r in rows if not r.event_date]
        missing_move=[r.event_id for r in rows if r.expected_move_pct is None]
        missing_conf=[r.event_id for r in rows if r.confidence is None]
        status='READY' if not dup and not missing_dates else 'FAILED'
        if status=='READY' and (stale or missing_move or missing_conf):status='DEGRADED'
        return {'status':status,'active_events':len(rows),'duplicate_keys':len(dup),'stale_events':len(stale),'missing_dates':len(missing_dates),'expected_move_missing':len(missing_move),'confidence_missing':len(missing_conf),'verified_at':datetime.now(timezone.utc).isoformat()}
