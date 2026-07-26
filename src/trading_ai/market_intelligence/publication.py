from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from trading_ai.persistence_normalization import strict_json_dumps, to_native


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    status: str
    rows: int
    latest_value: str | None
    required: bool
    message: str


@dataclass(frozen=True)
class ScannerReadinessResult:
    status: str
    as_of_date: str | None
    market_intelligence_timestamp: str | None
    option_snapshot_timestamp: str | None
    option_snapshot_id: str | None
    scanner_ready: bool
    decision_context_ready: bool
    checks: tuple[ReadinessCheck, ...]

    def to_dict(self) -> dict[str, Any]:
        return to_native(asdict(self))


class ScannerReadinessService:
    """Validates and atomically publishes one coherent downstream market state."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _scalar(self, sql: str, **params: Any) -> Any:
        return self.session.execute(text(sql), params).scalar_one_or_none()

    def evaluate(self) -> ScannerReadinessResult:
        mi = self.session.execute(text("""
            SELECT snapshot_timestamp, as_of_date
              FROM market_intelligence_snapshot
             ORDER BY snapshot_timestamp DESC
             LIMIT 1
        """)).mappings().one_or_none()
        option = self.session.execute(text("""
            SELECT snapshot_id, snapshot_timestamp, as_of_date, capture_status,
                   contracts_persisted, completeness_score
              FROM option_snapshot_run
             WHERE provider='POLYGON' AND contracts_persisted > 0
             ORDER BY snapshot_timestamp DESC
             LIMIT 1
        """)).mappings().one_or_none()

        mi_ts = mi["snapshot_timestamp"] if mi else None
        as_of = mi["as_of_date"] if mi else None
        option_ts = option["snapshot_timestamp"] if option else None
        option_id = option["snapshot_id"] if option else None

        specs = (
            ("price_history", "SELECT COUNT(*) FROM price_history", "SELECT MAX(date)::text FROM price_history", True),
            ("option_contract_history", "SELECT COUNT(*) FROM option_contract_history", "SELECT MAX(quote_date)::text FROM option_contract_history", True),
            ("option_contract_snapshot", "SELECT COUNT(*) FROM option_contract_snapshot", "SELECT MAX(snapshot_timestamp)::text FROM option_contract_snapshot", True),
            ("underlying_volatility_snapshot", "SELECT COUNT(*) FROM underlying_volatility_snapshot", "SELECT MAX(snapshot_timestamp)::text FROM underlying_volatility_snapshot", True),
            ("microstructure_liquidity_snapshot", "SELECT COUNT(*) FROM microstructure_liquidity_snapshot", "SELECT MAX(snapshot_timestamp)::text FROM microstructure_liquidity_snapshot", True),
            ("dealer_position_snapshot", "SELECT COUNT(*) FROM dealer_position_snapshot", "SELECT MAX(as_of_date)::text FROM dealer_position_snapshot", True),
            ("market_overview_snapshot", "SELECT COUNT(*) FROM market_overview_snapshot", "SELECT MAX(snapshot_timestamp)::text FROM market_overview_snapshot", True),
            ("market_intelligence_snapshot", "SELECT COUNT(*) FROM market_intelligence_snapshot", "SELECT MAX(snapshot_timestamp)::text FROM market_intelligence_snapshot", True),
            ("market_sentiment_snapshot", "SELECT COUNT(*) FROM market_sentiment_snapshot", "SELECT MAX(snapshot_timestamp)::text FROM market_sentiment_snapshot", True),
            ("market_risk_snapshot", "SELECT COUNT(*) FROM market_risk_snapshot", "SELECT MAX(snapshot_timestamp)::text FROM market_risk_snapshot", True),
        )
        checks: list[ReadinessCheck] = []
        for name, count_sql, latest_sql, required in specs:
            try:
                rows = int(self._scalar(count_sql) or 0)
                latest = self._scalar(latest_sql)
                status = "READY" if rows > 0 else "EMPTY"
                message = "Data is available." if rows > 0 else "Required table has no rows."
            except Exception as exc:
                rows, latest, status = 0, None, "FAILED"
                message = f"{type(exc).__name__}: {exc}"
            checks.append(ReadinessCheck(name, status, rows, str(latest) if latest is not None else None, required, message))

        if option:
            option_status = "READY" if option["capture_status"] == "READY" else "DEGRADED"
            checks.append(ReadinessCheck(
                "option_snapshot_completeness",
                option_status,
                int(option["contracts_persisted"] or 0),
                str(option["completeness_score"]),
                False,
                "Polygon option snapshot is complete." if option_status == "READY" else "Snapshot is usable but partial.",
            ))
        else:
            checks.append(ReadinessCheck("option_snapshot_completeness", "EMPTY", 0, None, True, "No persisted Polygon option snapshot."))

        required_failures = [c for c in checks if c.required and c.status not in {"READY", "DEGRADED"}]
        degraded = [c for c in checks if c.status == "DEGRADED"]
        status = "FAILED" if required_failures else "DEGRADED" if degraded else "READY"
        ready = status in {"READY", "DEGRADED"} and mi is not None and option is not None
        return ScannerReadinessResult(
            status=status,
            as_of_date=as_of.isoformat() if isinstance(as_of, date) else (str(as_of) if as_of else None),
            market_intelligence_timestamp=mi_ts.isoformat() if isinstance(mi_ts, datetime) else (str(mi_ts) if mi_ts else None),
            option_snapshot_timestamp=option_ts.isoformat() if isinstance(option_ts, datetime) else (str(option_ts) if option_ts else None),
            option_snapshot_id=str(option_id) if option_id else None,
            scanner_ready=ready,
            decision_context_ready=ready,
            checks=tuple(checks),
        )

    def publish(self, *, run_id: str, publication_name: str = "current_market_state") -> ScannerReadinessResult:
        result = self.evaluate()
        if not result.scanner_ready or not result.market_intelligence_timestamp or not result.as_of_date:
            return result
        params = {
            "name": publication_name,
            "run_id": run_id,
            "published_at": datetime.now(timezone.utc),
            "as_of": date.fromisoformat(result.as_of_date),
            "mi_ts": datetime.fromisoformat(result.market_intelligence_timestamp),
            "option_ts": datetime.fromisoformat(result.option_snapshot_timestamp) if result.option_snapshot_timestamp else None,
            "option_id": result.option_snapshot_id,
            "status": result.status,
            "scanner_ready": result.scanner_ready,
            "decision_ready": result.decision_context_ready,
            "details": strict_json_dumps(result.to_dict(), default=str),
        }
        self.session.execute(text("""
            INSERT INTO market_ingestion_publication
                (publication_name, run_id, published_at, as_of_date,
                 market_intelligence_timestamp, option_snapshot_timestamp,
                 option_snapshot_id, readiness_status, scanner_ready,
                 decision_context_ready, details_json, updated_at)
            VALUES
                (:name, :run_id, :published_at, :as_of, :mi_ts, :option_ts,
                 :option_id, :status, :scanner_ready, :decision_ready, :details, :published_at)
            ON CONFLICT (publication_name) DO UPDATE SET
                run_id=EXCLUDED.run_id,
                published_at=EXCLUDED.published_at,
                as_of_date=EXCLUDED.as_of_date,
                market_intelligence_timestamp=EXCLUDED.market_intelligence_timestamp,
                option_snapshot_timestamp=EXCLUDED.option_snapshot_timestamp,
                option_snapshot_id=EXCLUDED.option_snapshot_id,
                readiness_status=EXCLUDED.readiness_status,
                scanner_ready=EXCLUDED.scanner_ready,
                decision_context_ready=EXCLUDED.decision_context_ready,
                details_json=EXCLUDED.details_json,
                updated_at=EXCLUDED.updated_at
        """), params)
        self.session.commit()
        return result
