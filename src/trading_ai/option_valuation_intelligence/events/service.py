from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date, datetime, timezone

from dateutil.relativedelta import relativedelta
from sqlalchemy import select

from trading_ai.option_valuation_intelligence.models import OptionValuationEventModel

from .contracts import SourceEventRecord
from .policy import EventSyncPolicy
from .sources import (
    alpha_vantage_earnings,
    bea_calendar,
    bls_calendar,
    federal_reserve_fomc,
    SOURCE_FETCH_METADATA,
)

UTC = lambda: datetime.now(timezone.utc).isoformat()


def _canonical_payload(record: SourceEventRecord) -> dict:
    payload = asdict(record)
    for key in ("event_date", "meeting_start_date", "meeting_end_date"):
        if payload.get(key):
            payload[key] = payload[key].isoformat()
    if payload.get("event_time"):
        payload["event_time"] = payload["event_time"].isoformat()
    payload["event_components"] = list(payload.get("event_components") or [])
    return payload


def _hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class EventCalendarSynchronizationService:
    SOURCES = (
        ("ALPHA_VANTAGE", alpha_vantage_earnings),
        ("FEDERAL_RESERVE", federal_reserve_fomc),
        ("BLS", bls_calendar),
        ("BEA", bea_calendar),
    )

    def __init__(self, session_factory, policy: EventSyncPolicy | None = None):
        self.session_factory = session_factory
        self.policy = policy or EventSyncPolicy()
        self.last_source_results: dict[str, dict] = {}

    def fetch(self) -> list[SourceEventRecord]:
        all_rows: list[SourceEventRecord] = []
        source_results: dict[str, dict] = {}
        for source_name, fetcher in self.SOURCES:
            try:
                rows = fetcher(self.policy)
                all_rows.extend(rows)
                metadata = SOURCE_FETCH_METADATA.pop(source_name, {})
                source_results[source_name] = {
                    "status": metadata.get("status", "READY"),
                    "fetched": len(rows),
                    "error": metadata.get("error"),
                    "fetch_mode": metadata.get("fetch_mode", "LIVE"),
                }
            except Exception as exc:  # source isolation is deliberate
                source_results[source_name] = {
                    "status": "DEGRADED",
                    "fetched": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                }

        self.last_source_results = source_results
        if not all_rows:
            errors = "; ".join(
                f"{name}={result['error']}"
                for name, result in source_results.items()
                if result["error"]
            )
            raise RuntimeError(f"All event-calendar sources failed: {errors}")

        start = date.today()
        end = start + relativedelta(months=self.policy.horizon_months)
        return [record for record in all_rows if start <= record.event_date <= end]

    def synchronize(self, records: list[SourceEventRecord] | None = None) -> dict:
        records = records if records is not None else self.fetch()
        now = UTC()
        created = updated = unchanged = superseded = 0
        seen_keys_by_source: dict[str, set[str]] = {}
        with self.session_factory() as session:
            for record in records:
                seen_keys_by_source.setdefault(record.calendar_source, set()).add(record.source_event_key)
                payload = _canonical_payload(record)
                content_hash = _hash(payload)
                row = session.execute(
                    select(OptionValuationEventModel).where(
                        OptionValuationEventModel.calendar_source == record.calendar_source,
                        OptionValuationEventModel.source_event_key == record.source_event_key,
                    )
                ).scalar_one_or_none()
                if row is None:
                    row = OptionValuationEventModel(
                        event_id="M69-EVT-" + content_hash[:24].upper(),
                        symbol=record.symbol,
                        event_type=record.event_type,
                        event_date=record.event_date.isoformat(),
                        status="ACTIVE",
                        confidence=0.0,
                        source=record.calendar_source,
                        payload_json=record.raw_payload,
                        calendar_source=record.calendar_source,
                        source_event_key=record.source_event_key,
                        release_name=record.release_name,
                        event_time=record.event_time.isoformat() if record.event_time else None,
                        event_timezone=record.event_timezone,
                        event_session=record.event_session,
                        event_time_status=record.event_time_status,
                        date_status=record.date_status,
                        event_components_json=list(record.event_components),
                        meeting_start_date=(
                            record.meeting_start_date.isoformat()
                            if record.meeting_start_date
                            else None
                        ),
                        meeting_end_date=(
                            record.meeting_end_date.isoformat()
                            if record.meeting_end_date
                            else None
                        ),
                        first_seen_at=now,
                        last_seen_at=now,
                        source_updated_at=record.source_updated_at or now,
                        revision_number=1,
                        content_hash=content_hash,
                        record_origin="AUTOMATED",
                        evidence_json={"calendar": payload},
                    )
                    session.add(row)
                    created += 1
                elif row.content_hash == content_hash:
                    # Intentionally no row mutation for unchanged events.
                    unchanged += 1
                else:
                    updates = {
                        "symbol": record.symbol,
                        "event_type": record.event_type,
                        "event_date": record.event_date.isoformat(),
                        "status": "ACTIVE",
                        "source": record.calendar_source,
                        "release_name": record.release_name,
                        "event_time": (
                            record.event_time.isoformat() if record.event_time else None
                        ),
                        "event_timezone": record.event_timezone,
                        "event_session": record.event_session,
                        "event_time_status": record.event_time_status,
                        "date_status": record.date_status,
                        "event_components_json": list(record.event_components),
                        "meeting_start_date": (
                            record.meeting_start_date.isoformat()
                            if record.meeting_start_date
                            else None
                        ),
                        "meeting_end_date": (
                            record.meeting_end_date.isoformat()
                            if record.meeting_end_date
                            else None
                        ),
                        "payload_json": record.raw_payload,
                        "content_hash": content_hash,
                        "last_seen_at": now,
                        "source_updated_at": record.source_updated_at or now,
                        "revision_number": int(row.revision_number or 0) + 1,
                        "evidence_json": {"calendar": payload},
                    }
                    for name, value in updates.items():
                        setattr(row, name, value)
                    updated += 1
            # Authoritative reconciliation: only for sources that completed successfully.
            # Missing source-owned records are superseded, never deleted. This repairs prior
            # parser over-collection and handles provider date cancellations/revisions safely.
            successful_sources = {
                name for name, result in self.last_source_results.items()
                if result.get("status") == "READY"
            }
            for source_name in successful_sources:
                seen_keys = seen_keys_by_source.get(source_name, set())
                existing_rows = session.execute(
                    select(OptionValuationEventModel).where(
                        OptionValuationEventModel.calendar_source == source_name,
                        OptionValuationEventModel.record_origin == "AUTOMATED",
                        OptionValuationEventModel.status == "ACTIVE",
                    )
                ).scalars().all()
                for existing in existing_rows:
                    if existing.source_event_key not in seen_keys:
                        existing.status = "SUPERSEDED"
                        existing.superseded_at = now
                        existing.last_seen_at = now
                        superseded += 1
            session.commit()

        source_results = self.last_source_results or {
            "INJECTED_RECORDS": {
                "status": "READY",
                "fetched": len(records),
                "error": None,
            }
        }
        degraded_sources = [
            name for name, result in source_results.items() if result["status"] != "READY"
        ]
        return {
            "status": "DEGRADED" if degraded_sources else "READY",
            "horizon_months": self.policy.horizon_months,
            "fetched": len(records),
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "superseded": superseded,
            "duplicates_prevented": unchanged,
            "source_results": source_results,
            "degraded_sources": degraded_sources,
            "completed_at": now,
        }
