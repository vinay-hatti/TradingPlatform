from __future__ import annotations

from typing import Any
from sqlalchemy import text
from .analytics import distribution


class HistoricalEventOutcomeRepository:
    def distribution_for(self, session, *, symbol: str, event_type: str, minimum_samples: int = 3, limit: int = 40) -> tuple[float | None, int, dict[str, Any] | None]:
        symbol = str(symbol).upper()
        rows = session.execute(
            text("""
                SELECT realized_absolute_move_pct, symbol, event_type, event_date
                FROM institutional_event_outcomes
                WHERE status = 'FINAL'
                  AND realized_absolute_move_pct IS NOT NULL
                  AND event_type = :event_type
                  AND (UPPER(symbol) = :symbol OR UPPER(symbol) IN ('*','ALL'))
                ORDER BY event_date DESC
                LIMIT :limit
            """),
            {"symbol": symbol, "event_type": event_type, "limit": limit},
        ).mappings().all()
        scope = "SYMBOL_EVENT_TYPE"
        if len(rows) < minimum_samples:
            rows = session.execute(
                text("""
                    SELECT realized_absolute_move_pct, symbol, event_type, event_date
                    FROM institutional_event_outcomes
                    WHERE status = 'FINAL'
                      AND realized_absolute_move_pct IS NOT NULL
                      AND event_type = :event_type
                    ORDER BY event_date DESC
                    LIMIT :limit
                """),
                {"event_type": event_type, "limit": limit},
            ).mappings().all()
            scope = "EVENT_TYPE_POOL"
        dist = distribution(row["realized_absolute_move_pct"] for row in rows)
        if not dist:
            return None, 0, None
        evidence = dict(dist.__dict__)
        evidence.update({"scope": scope, "source": "institutional_event_outcomes", "events": [dict(row) for row in rows[:10]]})
        return dist.median, dist.sample_size, evidence
