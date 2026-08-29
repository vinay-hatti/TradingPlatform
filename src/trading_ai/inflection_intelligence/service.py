from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from math import ceil
import time
from uuid import uuid4

from sqlalchemy import desc, or_, select, text
from sqlalchemy.exc import OperationalError

from trading_ai.database.models import PriceHistory
from trading_ai.institutional_market_structure.database_models import (
    DealerPositionSnapshotModel,
    DealerStrikeProfileModel,
)
from trading_ai.institutional_options.models import (
    InstitutionalDecisionSnapshotModel,
    InstitutionalOpportunityModel,
)
from trading_ai.institutional_options.publication_scope import latest_stock_intelligence_publication
from trading_ai.market_intelligence.database_models import (
    SectorBreadthSnapshotModel,
    SectorMembershipModel,
)
from trading_ai.market_overview.database_models import (
    MarketBreadthSnapshotModel,
    MarketOverviewSnapshotModel,
)
from trading_ai.stock_intelligence.models import StockScannerCandidateModel

from .engine import Bar, InstitutionalInflectionEngine, POLICY_VERSION
from .models import (
    InflectionPublicationModel,
    InflectionSnapshotModel,
    InflectionTimelineEventModel,
)


def _json_default(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(
        f"Object of type {value.__class__.__name__} is not JSON serializable"
    )


def _json_safe(payload: object) -> object:
    """Normalize governed payloads through the production JSON contract.

    Temporal database values are serialized explicitly. Any other unsupported
    type or non-finite number fails before ORM persistence, preserving the
    previous authority instead of failing partway through a flush.
    """
    return json.loads(json.dumps(
        payload,
        default=_json_default,
        allow_nan=False,
        separators=(",", ":"),
    ))


def _canonical_hash(payload: object) -> str:
    normalized = _json_safe(payload)
    return sha256(json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _as_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _as_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


class InstitutionalInflectionService:
    PUBLICATION = "current_institutional_inflection"
    STOCK_PUBLICATION = "current_stock_intelligence"
    MARKET_PUBLICATION = "current_market_state"
    LOCK_NAME = "trading_ai:m68_inflection_authority"
    SNAPSHOT_RETENTION_RUNS = 40
    TIMELINE_RETENTION_EVENTS_PER_SYMBOL = 120
    MINIMUM_SECTOR_BREADTH_CONSTITUENTS = 5
    MINIMUM_SECTOR_BREADTH_CONFIDENCE = 60.0

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.engine = InstitutionalInflectionEngine()

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _stock_lineage(publication) -> dict:
        payload = dict(publication.payload_json or {})
        lineage = dict(payload.get("lineage") or {})
        return {
            "market_as_of_date": str(
                lineage.get("market_as_of_date")
                or payload.get("market_as_of_date") or ""
            )[:10] or None,
            "option_snapshot_id": (
                lineage.get("option_snapshot_id")
                or payload.get("option_snapshot_id")
            ),
            "snapshot_timestamp": publication.snapshot_timestamp,
        }

    def _latest_stock_publication(self, session, build_mode: str):
        publication = latest_stock_intelligence_publication(
            session, self.STOCK_PUBLICATION,
            require_materialized=build_mode != "UNDERLYING_PRIMARY",
        )
        if publication is None:
            kind = "usable" if build_mode == "UNDERLYING_PRIMARY" else "materialized"
            raise LookupError(f"No {kind} Stock Intelligence publication found")
        return publication

    def _breadth_payload(
        self,
        session,
        *,
        symbol: str,
        source_as_of_date: date,
        publication_timestamp: datetime,
    ) -> dict:
        """Resolve exact, point-in-time breadth without future leakage.

        Direct sector ETF evidence is preferred. Company symbols resolve their
        effective sector membership as of the source date. A governed market
        breadth snapshot is the fallback. Every snapshot must have the exact
        source date and must exist no later than the Stock Intelligence
        publication that owns the Inflection build.
        """
        sector_rows = session.execute(
            select(SectorBreadthSnapshotModel).where(
                SectorBreadthSnapshotModel.as_of_date == source_as_of_date,
                SectorBreadthSnapshotModel.snapshot_timestamp
                <= publication_timestamp,
            )
        ).scalars().all()

        def usable(row) -> bool:
            return bool(
                int(row.constituent_count or 0)
                >= self.MINIMUM_SECTOR_BREADTH_CONSTITUENTS
                and float(row.confidence or 0.0)
                >= self.MINIMUM_SECTOR_BREADTH_CONFIDENCE
            )

        direct = [
            row for row in sector_rows
            if str(row.sector_etf or "").upper() == symbol.upper() and usable(row)
        ]
        membership = None
        candidates = direct
        resolution = "DIRECT_SECTOR_ETF"
        if not candidates:
            membership = session.execute(
                select(SectorMembershipModel).where(
                    SectorMembershipModel.symbol == symbol.upper(),
                    SectorMembershipModel.effective_from <= source_as_of_date,
                    or_(
                        SectorMembershipModel.effective_to.is_(None),
                        SectorMembershipModel.effective_to >= source_as_of_date,
                    ),
                ).order_by(
                    desc(SectorMembershipModel.effective_from),
                    desc(SectorMembershipModel.confidence),
                )
            ).scalars().first()
            if membership is not None:
                expected_etf = str(membership.sector_etf or "").upper()
                candidates = [
                    row for row in sector_rows
                    if str(row.sector or "") == str(membership.sector or "")
                    and usable(row)
                ]
                candidates.sort(key=lambda row: (
                    str(row.sector_etf or "").upper() == expected_etf,
                    row.snapshot_timestamp,
                    int(row.constituent_count or 0),
                    float(row.confidence or 0.0),
                ), reverse=True)
                resolution = "EFFECTIVE_SECTOR_MEMBERSHIP"
        else:
            candidates.sort(key=lambda row: (
                row.snapshot_timestamp,
                int(row.constituent_count or 0),
                float(row.confidence or 0.0),
            ), reverse=True)

        if candidates:
            row = candidates[0]
            return {
                "score": float(row.breadth_score),
                "available": True,
                "resolution": resolution,
                "source_table": "sector_breadth_snapshot",
                "snapshot_timestamp": row.snapshot_timestamp.isoformat(),
                "as_of_date": str(row.as_of_date),
                "sector": row.sector,
                "sector_etf": row.sector_etf,
                "constituent_count": int(row.constituent_count or 0),
                "confidence": float(row.confidence or 0.0),
                "provenance": row.provenance,
                "membership_effective_from": (
                    None if membership is None else str(membership.effective_from)
                ),
            }

        market = session.execute(
            select(MarketBreadthSnapshotModel).where(
                MarketBreadthSnapshotModel.as_of_date == source_as_of_date,
                MarketBreadthSnapshotModel.snapshot_timestamp
                <= publication_timestamp,
            ).order_by(
                desc(MarketBreadthSnapshotModel.snapshot_timestamp),
                desc(MarketBreadthSnapshotModel.evaluated_symbols),
            )
        ).scalars().first()
        if market is not None and int(market.evaluated_symbols or 0) >= 25:
            return {
                "score": float(market.breadth_score),
                "available": True,
                "resolution": "CANONICAL_MARKET_FALLBACK",
                "source_table": "market_breadth_snapshot",
                "snapshot_timestamp": market.snapshot_timestamp.isoformat(),
                "as_of_date": str(market.as_of_date),
                "universe_name": market.universe_name,
                "evaluated_symbols": int(market.evaluated_symbols or 0),
                "breadth_regime": market.breadth_regime,
            }

        overview = session.execute(
            select(MarketOverviewSnapshotModel).where(
                MarketOverviewSnapshotModel.as_of_date == source_as_of_date,
                MarketOverviewSnapshotModel.snapshot_timestamp
                <= publication_timestamp,
            ).order_by(desc(MarketOverviewSnapshotModel.snapshot_timestamp))
        ).scalars().first()
        if overview is not None:
            return {
                "score": float(overview.breadth_score),
                "available": True,
                "resolution": "MARKET_OVERVIEW_FALLBACK",
                "source_table": "market_overview_snapshot",
                "snapshot_timestamp": overview.snapshot_timestamp.isoformat(),
                "as_of_date": str(overview.as_of_date),
                "confidence": float(overview.confidence_score or 0.0),
                "breadth_regime": overview.breadth_regime,
            }
        return {
            "score": None,
            "available": False,
            "resolution": "ABSTAIN_NO_POINT_IN_TIME_BREADTH",
            "source_table": None,
            "snapshot_timestamp": None,
            "as_of_date": source_as_of_date.isoformat(),
        }

    @staticmethod
    def _market_lineage(session) -> dict:
        row = session.execute(text("""
            SELECT option_snapshot_id, option_snapshot_timestamp,
                   as_of_date, readiness_status, scanner_ready
              FROM market_ingestion_publication
             WHERE publication_name = :name
             LIMIT 1
        """), {"name": InstitutionalInflectionService.MARKET_PUBLICATION}).mappings().one_or_none()
        return dict(row) if row else {}

    @staticmethod
    def _aggregate(rows: list[Bar], timeframe: str) -> list[Bar]:
        if timeframe == "1d":
            return rows
        buckets: dict[tuple[int, ...], list[Bar]] = defaultdict(list)
        for bar in rows:
            as_of = _as_date(bar.as_of)
            if as_of is None:
                continue
            if timeframe == "1w":
                iso = as_of.isocalendar()
                key = (iso.year, iso.week)
            elif timeframe == "1mo":
                key = (as_of.year, as_of.month)
            else:
                raise ValueError(f"Unsupported Inflection timeframe: {timeframe}")
            buckets[key].append(bar)
        result: list[Bar] = []
        for key in sorted(buckets):
            group = buckets[key]
            result.append(Bar(
                close=group[-1].close,
                high=max(item.high for item in group),
                low=min(item.low for item in group),
                volume=sum(item.volume for item in group),
                as_of=group[-1].as_of,
            ))
        return result

    def _bars(self, session, symbol: str, *, timeframe: str,
              market_as_of_date: date | None) -> list[Bar]:
        lookback = {"1d": 120, "1w": 500, "1mo": 1300}[timeframe]
        query = select(PriceHistory).where(PriceHistory.symbol == symbol)
        if market_as_of_date is not None:
            query = query.where(PriceHistory.date <= market_as_of_date)
        records = session.execute(
            query.order_by(PriceHistory.date.desc()).limit(lookback)
        ).scalars().all()
        daily = [Bar(
            close=float(row.close or 0.0),
            high=float(row.high or row.close or 0.0),
            low=float(row.low or row.close or 0.0),
            volume=float(row.volume or 0.0),
            as_of=str(row.date),
        ) for row in reversed(records)]
        return self._aggregate(daily, timeframe)[-90:]

    def _dealer_payload(self, session, symbol: str,
                        *, option_as_of_date: date | None) -> dict:
        query = select(DealerPositionSnapshotModel).where(
            DealerPositionSnapshotModel.symbol == symbol
        )
        if option_as_of_date is not None:
            query = query.where(
                DealerPositionSnapshotModel.as_of_date == option_as_of_date
            )
        row = session.execute(
            query.order_by(desc(DealerPositionSnapshotModel.as_of_date))
        ).scalars().first()
        if row is None:
            return {}
        bull = float(row.bull_probability or 0.0)
        bear = float(row.bear_probability or 0.0)
        probability_scale = 1.0 if max(bull, bear) <= 1.0 else 0.01
        migration = 50.0 if row.gamma_flip_distance_pct is None else max(
            0.0, min(100.0, 100.0 - abs(float(row.gamma_flip_distance_pct)) * 8.0)
        )
        hedge = max(0.0, min(
            100.0,
            50.0 + float(row.net_vanna_exposure or 0.0) / 1_000_000.0
            + float(row.net_charm_exposure or 0.0) / 1_000_000.0,
        ))
        return {
            "directional_score": (bull - bear) * probability_scale * 100.0,
            "bull_probability": bull,
            "bear_probability": bear,
            "gamma_score": float(row.institutional_positioning_score or 50.0),
            "wall_migration_score": migration,
            "hedge_pressure_score": hedge,
            "gamma_regime": row.gamma_regime,
            "gamma_flip": row.gamma_flip,
            "put_wall": row.primary_put_wall,
            "call_wall": row.primary_call_wall,
            "atm_iv": None if row.atm_iv is None else float(row.atm_iv),
            "confidence_score": float(row.confidence_score or 0.0),
            "quote_coverage_pct": float(row.quote_coverage_pct or 0.0),
            "as_of_date": str(row.as_of_date),
            "quote_date": str(row.quote_date),
            "source_contract_count": int(row.source_contract_count or 0),
            "executable_contract_count": int(row.executable_contract_count or 0),
        }

    @staticmethod
    def _option_spread_pct(session, symbol: str,
                           *, option_as_of_date: date | None) -> float | None:
        query = select(DealerStrikeProfileModel).where(
            DealerStrikeProfileModel.symbol == symbol,
            DealerStrikeProfileModel.trade_eligible.is_(True),
        )
        if option_as_of_date is not None:
            query = query.where(
                DealerStrikeProfileModel.as_of_date == option_as_of_date
            )
        rows = session.execute(query).scalars().all()
        values = [
            float(value)
            for row in rows
            for value in (row.call_spread_pct, row.put_spread_pct)
            if value is not None and float(value) >= 0.0
        ]
        return round(sum(values) / len(values), 6) if values else None

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = min(len(ordered) - 1,
                    max(0, ceil(percentile / 100.0 * len(ordered)) - 1))
        return round(float(ordered[index]), 4)

    @classmethod
    def _diagnostics(cls, results: list[dict]) -> dict:
        strengths = [float(item["signal_strength"]) for item in results]
        signed = [float(item["directional_score"]) for item in results]
        histogram = {f"{lo:02d}-{lo + 9:02d}": 0 for lo in range(0, 100, 10)}
        histogram["100"] = 0
        for score in strengths:
            key = "100" if score >= 100 else f"{int(score // 10) * 10:02d}-{int(score // 10) * 10 + 9:02d}"
            histogram[key] += 1
        components: dict[str, list[float]] = defaultdict(list)
        for item in results:
            for name, value in (item.get("components") or {}).items():
                components[str(name)].append(float(value))
        def counts(key: str) -> dict[str, int]:
            names = sorted({str(item.get(key)) for item in results})
            return {name: sum(str(item.get(key)) == name for item in results)
                    for name in names}
        return {
            "minimum_strength": round(min(strengths), 4) if strengths else 0.0,
            "median_strength": cls._percentile(strengths, 50),
            "p90_strength": cls._percentile(strengths, 90),
            "maximum_strength": round(max(strengths), 4) if strengths else 0.0,
            "minimum_directional_score": round(min(signed), 4) if signed else 0.0,
            "median_directional_score": cls._percentile(signed, 50),
            "maximum_directional_score": round(max(signed), 4) if signed else 0.0,
            "histogram": histogram,
            "transition_counts": counts("transition_state"),
            "direction_counts": counts("direction"),
            "disposition_counts": counts("disposition"),
            "component_averages": {
                name: round(sum(values) / len(values), 4)
                for name, values in sorted(components.items()) if values
            },
            "thresholds": dict(InstitutionalInflectionEngine.THRESHOLDS),
        }

    def build(self, *, limit: int | None = None, timeframe: str = "1d",
              build_mode: str = "MANUAL", max_retries: int = 3) -> dict:
        normalized_mode = str(build_mode).upper()
        if normalized_mode not in {
            "UNDERLYING_PRIMARY", "OPTIONS_ENRICHMENT", "MANUAL"
        }:
            raise ValueError(f"Unsupported M68 build mode: {build_mode}")
        if timeframe not in {"1d", "1w", "1mo"}:
            raise ValueError(f"Unsupported Inflection timeframe: {timeframe}")
        for attempt in range(1, max_retries + 1):
            try:
                return self._build_once(
                    limit=limit, timeframe=timeframe, build_mode=normalized_mode
                )
            except OperationalError:
                if attempt >= max_retries:
                    raise
                try:
                    self.session_factory.kw.get("bind").dispose()
                except Exception:
                    pass
                time.sleep(min(2 ** (attempt - 1), 4))
        raise RuntimeError("Inflection build retry loop exhausted")

    def _build_once(self, *, limit: int | None, timeframe: str,
                    build_mode: str) -> dict:
        with self.session_factory() as session:
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_name))"),
                {"lock_name": self.LOCK_NAME},
            )
            stock_publication = self._latest_stock_publication(session, build_mode)
            source_run = str(stock_publication.scanner_run_id)
            stock_lineage = self._stock_lineage(stock_publication)
            market_lineage = self._market_lineage(session)
            source_as_of = _as_date(stock_lineage.get("market_as_of_date"))
            option_as_of = _as_date(market_lineage.get("as_of_date"))
            option_snapshot_id = market_lineage.get("option_snapshot_id")
            if source_as_of is None:
                raise ValueError(
                    "Stock Intelligence authority is missing market_as_of_date lineage"
                )
            stock_publication_timestamp = _as_datetime(
                stock_publication.snapshot_timestamp
            )
            if stock_publication_timestamp is None:
                raise ValueError(
                    "Stock Intelligence authority is missing a valid publication timestamp"
                )

            query = select(StockScannerCandidateModel).where(
                StockScannerCandidateModel.scanner_run_id == source_run
            ).order_by(
                desc(StockScannerCandidateModel.score),
                StockScannerCandidateModel.symbol,
            )
            if limit:
                query = query.limit(limit)
            candidates = session.execute(query).scalars().all()
            if not candidates:
                raise LookupError(
                    f"No Stock Intelligence candidates resolved for {source_run}"
                )

            computed: list[tuple[object, dict]] = []
            skipped: list[dict] = []
            for candidate in candidates:
                bars = self._bars(
                    session, candidate.symbol, timeframe=timeframe,
                    market_as_of_date=source_as_of,
                )
                if len(bars) < 25:
                    skipped.append({
                        "symbol": candidate.symbol,
                        "reason": "INSUFFICIENT_TIMEFRAME_HISTORY",
                        "bars": len(bars),
                        "timeframe": timeframe,
                    })
                    continue
                original_payload = dict(candidate.payload_json or {})
                breadth = self._breadth_payload(
                    session,
                    symbol=candidate.symbol,
                    source_as_of_date=source_as_of,
                    publication_timestamp=stock_publication_timestamp,
                )
                breadth_raw = breadth.get("score")
                dealer = self._dealer_payload(
                    session, candidate.symbol, option_as_of_date=option_as_of
                )
                spread = self._option_spread_pct(
                    session, candidate.symbol, option_as_of_date=option_as_of
                )
                governed_inputs = dict(original_payload)
                governed_inputs["implied_volatility"] = dealer.get("atm_iv")
                governed_inputs["spread_pct"] = spread
                result = self.engine.evaluate(
                    candidate.symbol,
                    bars,
                    candidate_payload=governed_inputs,
                    dealer_payload=dealer,
                    breadth_score=(
                        None if breadth_raw is None else float(breadth_raw)
                    ),
                    timeframe=timeframe,
                    build_mode=build_mode,
                )
                dealer_as_of = dealer.get("as_of_date")
                breadth_exact = bool(
                    breadth.get("available")
                    and breadth.get("as_of_date") == source_as_of.isoformat()
                    and _as_datetime(breadth.get("snapshot_timestamp")) is not None
                    and _as_datetime(breadth.get("snapshot_timestamp"))
                    <= stock_publication_timestamp
                )
                options_exact = bool(
                    option_snapshot_id and option_as_of
                    and dealer_as_of == option_as_of.isoformat()
                    and dealer.get("atm_iv") is not None
                    and spread is not None
                )
                if build_mode == "OPTIONS_ENRICHMENT" and breadth_exact and options_exact:
                    coverage_status = "CURRENT_EXACT"
                elif not breadth_exact and not options_exact and build_mode == "OPTIONS_ENRICHMENT":
                    coverage_status = "ABSTAIN_INCOMPLETE_BREADTH_AND_OPTIONS"
                elif not breadth_exact:
                    coverage_status = "ABSTAIN_INCOMPLETE_BREADTH"
                elif build_mode == "UNDERLYING_PRIMARY":
                    coverage_status = "UNDERLYING_CURRENT_OPTIONS_OPTIONAL"
                else:
                    coverage_status = "ABSTAIN_INCOMPLETE_OPTIONS"
                lineage = {
                    "stock_scanner_run_id": source_run,
                    "stock_publication_name": self.STOCK_PUBLICATION,
                    "stock_publication_timestamp": stock_publication.snapshot_timestamp,
                    "source_as_of_date": (
                        None if source_as_of is None else source_as_of.isoformat()
                    ),
                    "option_snapshot_id": option_snapshot_id,
                    "option_snapshot_timestamp": (
                        str(market_lineage.get("option_snapshot_timestamp") or "")
                        or None
                    ),
                    "option_as_of_date": (
                        None if option_as_of is None else option_as_of.isoformat()
                    ),
                    "dealer_as_of_date": dealer_as_of,
                    "build_mode": build_mode,
                    "component_freshness": {
                        "underlying": "CURRENT_EXACT",
                        "breadth": (
                            "CURRENT_EXACT" if breadth_exact
                            else "NOT_CURRENT_EXACT"
                        ),
                        "dealer_options": (
                            "CURRENT_EXACT" if options_exact else "NOT_CURRENT_EXACT"
                        ),
                    },
                    "breadth": breadth,
                }
                result["lineage"] = lineage
                result["coverage_status"] = coverage_status
                result = _json_safe(result)
                result["input_fingerprint"] = _canonical_hash({
                    "engine_input_fingerprint": result["input_fingerprint"],
                    "lineage": lineage,
                })
                result["state_hash"] = _canonical_hash(result)
                computed.append((candidate, result))

            expected = len(candidates)
            built = len(computed)
            if skipped or built != expected:
                session.rollback()
                return {
                    "status": "INVALID",
                    "cycle_outcome": "AUTHORITY_PRESERVED_INCOMPLETE_COVERAGE",
                    "source_run_id": source_run,
                    "expected": expected,
                    "built": built,
                    "skipped": len(skipped),
                    "skipped_details": skipped,
                    "coverage_status": "INCOMPLETE",
                    "policy_version": POLICY_VERSION,
                }

            authority_fingerprint = _canonical_hash({
                "policy_version": POLICY_VERSION,
                "source_run_id": source_run,
                "source_as_of_date": (
                    None if source_as_of is None else source_as_of.isoformat()
                ),
                "option_snapshot_id": option_snapshot_id,
                "build_mode": build_mode,
                "timeframe": timeframe,
                "inputs": sorted(
                    (result["symbol"], result["input_fingerprint"])
                    for _, result in computed
                ),
            })
            publication = session.execute(
                select(InflectionPublicationModel).where(
                    InflectionPublicationModel.publication_name == self.PUBLICATION
                )
            ).scalars().first()
            existing_count = len(session.execute(
                select(InflectionSnapshotModel.snapshot_id).where(
                    InflectionSnapshotModel.publication_name == self.PUBLICATION,
                    InflectionSnapshotModel.source_run_id == source_run,
                    InflectionSnapshotModel.timeframe == timeframe,
                )
            ).scalars().all())
            if (
                publication is not None
                and publication.source_run_id == source_run
                and publication.authority_input_fingerprint == authority_fingerprint
                and existing_count == expected
            ):
                session.rollback()
                return {
                    "status": publication.status,
                    "cycle_outcome": "NOOP_UNCHANGED_AUTHORITY",
                    "authoritative_rebuild_performed": False,
                    "source_run_id": source_run,
                    "built": expected,
                    "skipped": 0,
                    "coverage_status": publication.coverage_status,
                    "authority_input_fingerprint": authority_fingerprint,
                    "published_at": publication.published_at,
                    "policy_version": POLICY_VERSION,
                }

            return self._activate(
                session=session,
                publication=publication,
                stock_publication=stock_publication,
                computed=computed,
                expected=expected,
                source_run=source_run,
                source_as_of=source_as_of,
                option_snapshot_id=option_snapshot_id,
                authority_fingerprint=authority_fingerprint,
                timeframe=timeframe,
                build_mode=build_mode,
            )

    def _activate(self, *, session, publication, stock_publication,
                  computed: list[tuple[object, dict]], expected: int,
                  source_run: str, source_as_of: date | None,
                  option_snapshot_id: str | None,
                  authority_fingerprint: str, timeframe: str,
                  build_mode: str) -> dict:
        published_at = self.now()
        timeline_events = 0
        exact_opportunity_count = 0
        for candidate, result in computed:
            existing = session.execute(
                select(InflectionSnapshotModel).where(
                    InflectionSnapshotModel.publication_name == self.PUBLICATION,
                    InflectionSnapshotModel.source_run_id == source_run,
                    InflectionSnapshotModel.symbol == candidate.symbol,
                    InflectionSnapshotModel.timeframe == timeframe,
                )
            ).scalars().first()
            previous = session.execute(
                select(InflectionSnapshotModel).where(
                    InflectionSnapshotModel.publication_name == self.PUBLICATION,
                    InflectionSnapshotModel.symbol == candidate.symbol,
                    InflectionSnapshotModel.timeframe == timeframe,
                ).order_by(desc(InflectionSnapshotModel.snapshot_timestamp))
            ).scalars().first()
            previous_semantic = previous.semantic_state_hash if previous else None
            previous_transition_state = (
                previous.transition_state if previous else None
            )
            model = existing or InflectionSnapshotModel(
                snapshot_id=f"M68-INF-{uuid4().hex.upper()}",
                publication_name=self.PUBLICATION,
                source_run_id=source_run,
                symbol=candidate.symbol,
                timeframe=timeframe,
                direction=result["direction"],
                transition_state=result["transition_state"],
                directional_score=result["directional_score"],
                signal_strength=result["signal_strength"],
                inflection_score=result["inflection_score"],
                confidence=result["confidence"],
                input_quality=result["input_quality"],
                disposition=result["disposition"],
                horizon_min_sessions=result["horizon_min_sessions"],
                horizon_max_sessions=result["horizon_max_sessions"],
                input_fingerprint=result["input_fingerprint"],
                semantic_state_hash=result["semantic_state_hash"],
                state_hash=result["state_hash"],
                source_as_of_date=str(result["lineage"].get("source_as_of_date") or ""),
                option_snapshot_id=option_snapshot_id,
                dealer_as_of_date=result["lineage"].get("dealer_as_of_date"),
                coverage_status=result["coverage_status"],
                snapshot_timestamp=published_at,
                payload_json=result,
            )
            for field in (
                "direction", "transition_state", "directional_score",
                "signal_strength", "inflection_score", "confidence",
                "input_quality", "disposition", "horizon_min_sessions",
                "horizon_max_sessions", "input_fingerprint",
                "semantic_state_hash", "state_hash", "coverage_status",
            ):
                setattr(model, field, result[field])
            model.source_as_of_date = str(
                result["lineage"].get("source_as_of_date") or ""
            )
            model.option_snapshot_id = option_snapshot_id
            model.dealer_as_of_date = result["lineage"].get("dealer_as_of_date")
            model.snapshot_timestamp = published_at
            model.payload_json = result
            if existing is None:
                session.add(model)

            if previous_semantic != result["semantic_state_hash"]:
                event_fingerprint = _canonical_hash({
                    "symbol": candidate.symbol,
                    "timeframe": timeframe,
                    "source_run_id": source_run,
                    "previous_semantic_state_hash": previous_semantic,
                    "semantic_state_hash": result["semantic_state_hash"],
                    "input_fingerprint": result["input_fingerprint"],
                })
                already = session.execute(
                    select(InflectionTimelineEventModel.event_id).where(
                        InflectionTimelineEventModel.event_fingerprint
                        == event_fingerprint
                    )
                ).scalar_one_or_none()
                if already is None:
                    session.add(InflectionTimelineEventModel(
                        event_id=f"M68-TL-{uuid4().hex.upper()}",
                        symbol=candidate.symbol,
                        timeframe=timeframe,
                        source_run_id=source_run,
                        previous_transition_state=previous_transition_state,
                        transition_state=result["transition_state"],
                        transition_reason=(
                            "INITIAL_SEMANTIC_STATE"
                            if previous is None else "SEMANTIC_STATE_CHANGED"
                        ),
                        directional_score=result["directional_score"],
                        signal_strength=result["signal_strength"],
                        inflection_score=result["inflection_score"],
                        confidence=result["confidence"],
                        semantic_state_hash=result["semantic_state_hash"],
                        event_fingerprint=event_fingerprint,
                        state_hash=result["state_hash"],
                        event_timestamp=published_at,
                        payload_json=result,
                    ))
                    timeline_events += 1

            candidate_payload = dict(candidate.payload_json or {})
            candidate_payload["inflection_intelligence"] = result
            candidate.payload_json = candidate_payload
            opportunities = session.execute(
                select(InstitutionalOpportunityModel).where(
                    InstitutionalOpportunityModel.stock_scanner_run_id == source_run,
                    InstitutionalOpportunityModel.symbol == candidate.symbol,
                )
            ).scalars().all()
            exact_opportunity_count += len(opportunities)
            for opportunity in opportunities:
                opportunity_payload = dict(opportunity.payload_json or {})
                opportunity_payload["inflection_intelligence"] = result
                opportunity.payload_json = opportunity_payload
                decision = session.execute(
                    select(InstitutionalDecisionSnapshotModel).where(
                        InstitutionalDecisionSnapshotModel.opportunity_id
                        == opportunity.opportunity_id
                    )
                ).scalars().first()
                if decision is not None:
                    decision_payload = dict(decision.payload_json or {})
                    decision_payload["inflection_intelligence"] = result
                    decision.payload_json = decision_payload

        results = [item[1] for item in computed]
        retired_snapshots = session.execute(text("""
            WITH ranked_runs AS (
                SELECT source_run_id,
                       ROW_NUMBER() OVER (
                           ORDER BY MAX(snapshot_timestamp) DESC, source_run_id DESC
                       ) AS run_rank
                  FROM institutional_inflection_snapshots
                 WHERE publication_name = :publication_name
                 GROUP BY source_run_id
            ), retired_runs AS (
                SELECT source_run_id
                  FROM ranked_runs
                 WHERE run_rank > :retention_runs
            )
            DELETE FROM institutional_inflection_snapshots s
             USING retired_runs r
             WHERE s.publication_name = :publication_name
               AND s.source_run_id = r.source_run_id
        """), {
            "publication_name": self.PUBLICATION,
            "retention_runs": self.SNAPSHOT_RETENTION_RUNS,
        }).rowcount
        retired_timeline_events = session.execute(text("""
            WITH ranked AS (
                SELECT event_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY symbol, timeframe
                           ORDER BY event_timestamp DESC, event_id DESC
                       ) AS event_rank
                  FROM institutional_inflection_timeline_events
            ), retired AS (
                SELECT event_id
                  FROM ranked
                 WHERE event_rank > :retention_events
            )
            DELETE FROM institutional_inflection_timeline_events t
             USING retired r
             WHERE t.event_id = r.event_id
        """), {
            "retention_events": self.TIMELINE_RETENTION_EVENTS_PER_SYMBOL,
        }).rowcount
        diagnostics = self._diagnostics(results)
        breadth_abstentions = sum(
            "INCOMPLETE_BREADTH" in item["coverage_status"]
            for item in results
        )
        options_abstentions = sum(
            "INCOMPLETE_OPTIONS" in item["coverage_status"]
            for item in results
        )
        governed_abstentions = sum(
            item["coverage_status"].startswith("ABSTAIN_")
            for item in results
        )
        coverage_status = (
            "COMPLETE" if governed_abstentions == 0
            else "COMPLETE_WITH_ABSTENTIONS"
        )
        status = "READY" if governed_abstentions == 0 else "DEGRADED"
        high = sum(
            item["disposition"] == "HIGH_CONVICTION" for item in results
        )
        summary = {
            "policy_version": POLICY_VERSION,
            "source_run_id": source_run,
            "source_as_of_date": (
                None if source_as_of is None else source_as_of.isoformat()
            ),
            "option_snapshot_id": option_snapshot_id,
            "expected": expected,
            "built": len(results),
            "skipped": 0,
            "high_conviction": high,
            "average_signal_strength": round(
                sum(float(item["signal_strength"]) for item in results)
                / len(results), 4
            ),
            "average_directional_score": round(
                sum(float(item["directional_score"]) for item in results)
                / len(results), 4
            ),
            "timeframe": timeframe,
            "build_mode": build_mode,
            "coverage_status": coverage_status,
            "governed_abstentions": governed_abstentions,
            "breadth_abstentions": breadth_abstentions,
            "options_abstentions": options_abstentions,
            "exact_opportunity_attachments": exact_opportunity_count,
            "timeline_events_created": timeline_events,
            "retired_snapshot_rows": int(retired_snapshots or 0),
            "retired_timeline_events": int(retired_timeline_events or 0),
            "retention_policy": {
                "snapshot_source_runs": self.SNAPSHOT_RETENTION_RUNS,
                "timeline_events_per_symbol_timeframe": (
                    self.TIMELINE_RETENTION_EVENTS_PER_SYMBOL
                ),
            },
            "authority_input_fingerprint": authority_fingerprint,
            "diagnostics": diagnostics,
        }
        if publication is None:
            publication = InflectionPublicationModel(
                publication_id=f"M68-PUB-{uuid4().hex.upper()}",
                publication_name=self.PUBLICATION,
                source_run_id=source_run,
                status=status,
                symbol_count=len(results),
                high_conviction_count=high,
                authority_input_fingerprint=authority_fingerprint,
                coverage_status=coverage_status,
                source_as_of_date=summary["source_as_of_date"],
                option_snapshot_id=option_snapshot_id,
                published_at=published_at,
                payload_json=summary,
            )
            session.add(publication)
        else:
            publication.source_run_id = source_run
            publication.status = status
            publication.symbol_count = len(results)
            publication.high_conviction_count = high
            publication.authority_input_fingerprint = authority_fingerprint
            publication.coverage_status = coverage_status
            publication.source_as_of_date = summary["source_as_of_date"]
            publication.option_snapshot_id = option_snapshot_id
            publication.published_at = published_at
            publication.payload_json = summary
        session.commit()
        return {
            "status": status,
            "cycle_outcome": "AUTHORITY_REBUILT",
            "authoritative_rebuild_performed": True,
            **summary,
            "published_at": published_at,
        }

    def current(self, *, limit: int = 100) -> dict:
        with self.session_factory() as session:
            publication = session.execute(
                select(InflectionPublicationModel).where(
                    InflectionPublicationModel.publication_name == self.PUBLICATION
                )
            ).scalars().first()
            rows = []
            if publication is not None:
                rows = session.execute(
                    select(InflectionSnapshotModel).where(
                        InflectionSnapshotModel.publication_name == self.PUBLICATION,
                        InflectionSnapshotModel.source_run_id
                        == publication.source_run_id,
                    ).order_by(
                        desc(InflectionSnapshotModel.signal_strength),
                        InflectionSnapshotModel.symbol,
                    ).limit(limit)
                ).scalars().all()
            return {
                "publication": None if publication is None else {
                    "publication_id": publication.publication_id,
                    "status": publication.status,
                    "source_run_id": publication.source_run_id,
                    "symbol_count": publication.symbol_count,
                    "high_conviction_count": publication.high_conviction_count,
                    "authority_input_fingerprint": (
                        publication.authority_input_fingerprint
                    ),
                    "coverage_status": publication.coverage_status,
                    "source_as_of_date": publication.source_as_of_date,
                    "option_snapshot_id": publication.option_snapshot_id,
                    "published_at": publication.published_at,
                    "payload": publication.payload_json,
                },
                "snapshots": [row.payload_json for row in rows],
            }
