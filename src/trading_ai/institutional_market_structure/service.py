from __future__ import annotations

import csv
import io
import json
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter
from typing import Iterable

from sqlalchemy import delete, insert, select

from trading_ai.database.repositories.option_chain import OptionChainRepository
from trading_ai.database.session import create_session
from trading_ai.market.models import PriceHistory
from .contracts import DealerPositioningPolicy, InstitutionalMarketStructureSnapshot
from .engine import InstitutionalMarketStructureEngine
from .reporting import write_html_report
from .serialization import write_snapshot


class InstitutionalMarketStructureService:
    def __init__(self, policy: DealerPositioningPolicy | None = None):
        self.policy = policy or DealerPositioningPolicy()
        self.engine = InstitutionalMarketStructureEngine(self.policy)
        self.last_profile: dict[str, float] = {}

    def run(
        self,
        symbol: str,
        as_of: date,
        output_dir: Path = Path("reports/m44"),
        persist: bool = True,
        write_reports: bool = True,
        preloaded: dict | None = None,
    ) -> InstitutionalMarketStructureSnapshot:
        """Backward-compatible single-symbol service path.

        M68.2.1.15.8.4 keeps this path intact for fail-fast mode, adapters, and
        operational fallback.  The optimized universe refresh uses
        ``compute_preloaded`` + ``persist_many`` instead so worker threads never
        write to PostgreSQL.
        """
        symbol = symbol.upper()
        total_started = perf_counter()
        input_started = perf_counter()
        persist_profile: dict[str, float] = {}
        with create_session() as session:
            repo = OptionChainRepository(session)
            if preloaded is None:
                rows = repo.get_latest_snapshot(symbol, as_of)
                if not rows:
                    raise ValueError(f"No persisted option snapshot found for {symbol} on or before {as_of}")
                qdate = max(r["quote_date"] for r in rows)
                price = session.scalar(
                    select(PriceHistory)
                    .where(PriceHistory.symbol == symbol, PriceHistory.date <= qdate)
                    .order_by(PriceHistory.date.desc())
                    .limit(1)
                )
                hist = list(
                    session.scalars(
                        select(PriceHistory)
                        .where(
                            PriceHistory.symbol == symbol,
                            PriceHistory.date >= qdate - timedelta(days=90),
                            PriceHistory.date <= qdate,
                        )
                        .order_by(PriceHistory.date)
                    )
                )
                previous = self._load_previous(session, symbol, as_of)
                source_table = repo.resolved_table_name or "option_contract_history"
                payload = {
                    "rows": rows,
                    "quote_date": qdate,
                    "price_close": None if price is None else float(price.close),
                    "history_closes": [float(x.close) for x in hist if x.close and x.close > 0],
                    "previous": previous,
                    "source_table": source_table,
                }
            else:
                payload = dict(preloaded)
            input_seconds = perf_counter() - input_started
            compute_started = perf_counter()
            snapshot = self.compute_preloaded(symbol, as_of, payload)
            compute_seconds = perf_counter() - compute_started
            if persist:
                persist_profile = self._persist(session, snapshot)

        report_started = perf_counter()
        if write_reports:
            self.write_report(snapshot, output_dir)
        report_seconds = perf_counter() - report_started
        self.last_profile = {
            "input_seconds": round(input_seconds, 6),
            "compute_seconds": round(compute_seconds, 6),
            "persistence_seconds": round(float(persist_profile.get("total_seconds", 0.0)), 6),
            "persistence_delete_seconds": round(float(persist_profile.get("delete_seconds", 0.0)), 6),
            "persistence_prepare_seconds": round(float(persist_profile.get("prepare_seconds", 0.0)), 6),
            "persistence_commit_seconds": round(float(persist_profile.get("commit_seconds", 0.0)), 6),
            "persistence_merge_seconds": round(float(persist_profile.get("merge_seconds", 0.0)), 6),
            "report_seconds": round(report_seconds, 6),
            "total_seconds": round(perf_counter() - total_started, 6),
        }
        return snapshot

    def compute_preloaded(
        self,
        symbol: str,
        as_of: date,
        preloaded: dict,
    ) -> InstitutionalMarketStructureSnapshot:
        """Pure dealer computation from immutable, already-loaded inputs."""
        symbol = symbol.upper()
        rows = list(preloaded.get("rows") or ())
        qdate = preloaded.get("quote_date")
        price_close = preloaded.get("price_close")
        if price_close is None and preloaded.get("price") is not None:
            price_close = float(preloaded["price"].close)
        history_closes = list(preloaded.get("history_closes") or ())
        if not history_closes and preloaded.get("history") is not None:
            history_closes = [
                float(x.close) for x in (preloaded.get("history") or ()) if x.close and x.close > 0
            ]
        previous = preloaded.get("previous")
        source_table = str(preloaded.get("source_table") or "option_contract_history")

        if not rows or qdate is None:
            raise ValueError(f"No persisted option snapshot found for {symbol} on or before {as_of}")
        age = (as_of - qdate).days
        if age > self.policy.maximum_snapshot_age_days:
            raise ValueError(
                f"Latest option snapshot for {symbol} is {age} days old ({qdate}); "
                f"maximum allowed is {self.policy.maximum_snapshot_age_days}"
            )
        if price_close is None:
            raise ValueError(f"No persisted underlying price found for {symbol} on or before option snapshot {qdate}")

        realized = None
        closes = [float(x) for x in history_closes if x and x > 0]
        if len(closes) >= 21:
            from math import log, sqrt
            from statistics import pstdev

            returns = [log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
            realized = pstdev(returns[-20:]) * sqrt(252)

        return self.engine.analyze(
            symbol,
            as_of,
            float(price_close),
            rows,
            realized,
            source_table,
            previous,
        )

    @staticmethod
    def write_report(snapshot: InstitutionalMarketStructureSnapshot, output_dir: Path) -> None:
        target = output_dir / snapshot.option_snapshot_date
        write_snapshot(snapshot, target)
        write_html_report(snapshot, target / f"{snapshot.symbol.lower()}_{snapshot.as_of_date}.html")

    @staticmethod
    def _load_previous(session, symbol, as_of):
        from .database_models import DealerPositionSnapshotModel

        row = session.scalar(
            select(DealerPositionSnapshotModel)
            .where(
                DealerPositionSnapshotModel.symbol == symbol,
                DealerPositionSnapshotModel.as_of_date < as_of,
            )
            .order_by(DealerPositionSnapshotModel.as_of_date.desc())
            .limit(1)
        )
        if row is None:
            return None
        from .serialization import snapshot_from_dict

        try:
            return snapshot_from_dict(json.loads(row.payload_json))
        except Exception:
            return None

    @staticmethod
    def _summary_mapping(snapshot: InstitutionalMarketStructureSnapshot) -> dict:
        from .database_models import DealerPositionSnapshotModel

        model = DealerPositionSnapshotModel.from_snapshot(snapshot)
        return {column.name: getattr(model, column.name) for column in model.__table__.columns}

    @staticmethod
    def _strike_mapping(symbol: str, ad: date, item) -> dict:
        return {
            "symbol": symbol,
            "as_of_date": ad,
            "expiry": date.fromisoformat(item.expiry),
            "strike": item.strike,
            "dte": item.dte,
            "call_open_interest": item.call_open_interest,
            "put_open_interest": item.put_open_interest,
            "call_volume": item.call_volume,
            "put_volume": item.put_volume,
            "call_gamma_exposure": item.call_gamma_exposure,
            "put_gamma_exposure": item.put_gamma_exposure,
            "net_gamma_exposure": item.net_gamma_exposure,
            "call_delta_exposure": item.call_delta_exposure,
            "put_delta_exposure": item.put_delta_exposure,
            "net_delta_exposure": item.net_delta_exposure,
            "vanna_exposure": item.vanna_exposure,
            "charm_exposure": item.charm_exposure,
            "call_spread_pct": item.call_spread_pct,
            "put_spread_pct": item.put_spread_pct,
            "liquidity_score": item.liquidity_score,
            "dealer_pressure_score": item.dealer_pressure_score,
            "pin_score": item.pin_score,
            "market_structure_eligible": item.market_structure_eligible,
            "trade_eligible": item.trade_eligible,
        }

    @staticmethod
    def _expiration_mapping(symbol: str, ad: date, item) -> dict:
        return {
            "symbol": symbol,
            "as_of_date": ad,
            "expiry": date.fromisoformat(item.expiry),
            "dte": item.dte,
            "call_open_interest": item.call_open_interest,
            "put_open_interest": item.put_open_interest,
            "net_gamma_exposure": item.net_gamma_exposure,
            "net_delta_exposure": item.net_delta_exposure,
            "net_vanna_exposure": item.net_vanna_exposure,
            "net_charm_exposure": item.net_charm_exposure,
            "atm_implied_volatility": item.atm_implied_volatility,
            "expected_move": item.expected_move,
            "liquidity_score": item.liquidity_score,
        }

    @staticmethod
    def _surface_mapping(symbol: str, ad: date, item) -> dict:
        return {
            "symbol": symbol,
            "as_of_date": ad,
            "expiry": date.fromisoformat(item.expiry),
            "strike": item.strike,
            "option_type": item.option_type,
            "dte": item.dte,
            "moneyness": item.moneyness,
            "delta": item.delta,
            "implied_volatility": item.implied_volatility,
            "bid": item.bid,
            "ask": item.ask,
            "mid": item.mid,
            "spread_pct": item.spread_pct,
        }

    @staticmethod
    def _copy_scalar(value):
        if value is None:
            return r"\N"
        if isinstance(value, bool):
            return "t" if value else "f"
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value

    @classmethod
    def _postgres_copy_rows(cls, session, model, mappings: list[dict], *, copy_batch_size: int = 50_000) -> None:
        """COPY already-governed rows directly into the target inside the active transaction."""
        if not mappings:
            return
        table = model.__table__
        columns = [c.name for c in table.columns]
        preparer = session.bind.dialect.identifier_preparer
        qtable = preparer.quote(table.name)
        qcols = ", ".join(preparer.quote(c) for c in columns)
        raw = session.connection().connection
        driver = getattr(raw, "driver_connection", raw)
        cursor = driver.cursor()
        try:
            if not hasattr(cursor, "copy_expert"):
                raise RuntimeError("PostgreSQL DBAPI cursor does not expose copy_expert")
            copy_sql = f"COPY {qtable} ({qcols}) FROM STDIN WITH (FORMAT CSV, NULL '\\N')"
            for start in range(0, len(mappings), max(1, int(copy_batch_size))):
                buf = io.StringIO()
                writer = csv.writer(buf, lineterminator="\n")
                for mapping in mappings[start : start + copy_batch_size]:
                    writer.writerow([cls._copy_scalar(mapping.get(c)) for c in columns])
                buf.seek(0)
                cursor.copy_expert(copy_sql, buf)
        finally:
            cursor.close()

    @classmethod
    def persist_many(
        cls,
        snapshots: Iterable[InstitutionalMarketStructureSnapshot],
        *,
        batch_size: int = 10_000,
    ) -> dict[str, object]:
        """Persist one complete dealer refresh with PostgreSQL COPY and safe fallbacks.

        The output rows and transaction semantics are unchanged. PostgreSQL uses
        COPY inside the same governed delete/replace transaction. If COPY is not
        available or fails, the established SQLAlchemy bulk writer is retried; if
        that also fails, symbol-isolated persistence remains the final recovery path.
        """
        snapshots = tuple(snapshots)
        if not snapshots:
            return {
                "successful_symbols": tuple(), "failed_symbols": {}, "delete_seconds": 0.0,
                "prepare_seconds": 0.0, "insert_seconds": 0.0, "commit_seconds": 0.0,
                "total_seconds": 0.0, "mode": "NOOP",
            }

        from .database_models import (
            DealerExpirationProfileModel, DealerPositionSnapshotModel,
            DealerStrikeProfileModel, IVSurfaceSnapshotModel,
        )

        total_started = perf_counter()
        prepare_started = perf_counter()
        summaries=[]; strikes=[]; expirations=[]; surfaces=[]; symbols_by_date={}
        for snapshot in snapshots:
            ad = date.fromisoformat(snapshot.as_of_date)
            symbols_by_date.setdefault(ad, []).append(snapshot.symbol)
            summaries.append(cls._summary_mapping(snapshot))
            strikes.extend(cls._strike_mapping(snapshot.symbol, ad, x) for x in snapshot.strike_exposures)
            expirations.extend(cls._expiration_mapping(snapshot.symbol, ad, x) for x in snapshot.expiration_exposures)
            surfaces.extend(cls._surface_mapping(snapshot.symbol, ad, x) for x in snapshot.iv_surface)
        prepare_seconds = perf_counter() - prepare_started

        models_and_rows = (
            (DealerPositionSnapshotModel, summaries),
            (DealerStrikeProfileModel, strikes),
            (DealerExpirationProfileModel, expirations),
            (IVSurfaceSnapshotModel, surfaces),
        )

        def delete_current(session):
            started = perf_counter()
            for ad, symbols in symbols_by_date.items():
                for model, _ in models_and_rows:
                    session.execute(delete(model).where(model.symbol.in_(symbols), model.as_of_date == ad))
            return perf_counter() - started

        def sqlalchemy_insert(session):
            started = perf_counter()
            for model, mappings in models_and_rows:
                statement = insert(model)
                for pos in range(0, len(mappings), max(1, int(batch_size))):
                    session.execute(statement, mappings[pos : pos + batch_size])
            return perf_counter() - started

        copy_error = None
        if snapshots:
            try:
                with create_session() as session:
                    if session.bind.dialect.name != "postgresql":
                        raise RuntimeError("COPY path requires PostgreSQL")
                    delete_seconds = delete_current(session)
                    insert_started = perf_counter()
                    for model, mappings in models_and_rows:
                        cls._postgres_copy_rows(session, model, mappings)
                    insert_seconds = perf_counter() - insert_started
                    commit_started = perf_counter(); session.commit(); commit_seconds = perf_counter() - commit_started
                return {
                    "successful_symbols": tuple(x.symbol for x in snapshots), "failed_symbols": {},
                    "delete_seconds": round(delete_seconds,6), "prepare_seconds": round(prepare_seconds,6),
                    "insert_seconds": round(insert_seconds,6), "commit_seconds": round(commit_seconds,6),
                    "total_seconds": round(perf_counter()-total_started,6),
                    "mode": "POSTGRES_COPY_SINGLE_WRITER", "copy_used": True,
                    "summary_rows": len(summaries), "strike_rows": len(strikes),
                    "expiration_rows": len(expirations), "surface_rows": len(surfaces),
                }
            except Exception as exc:
                copy_error = f"{type(exc).__name__}: {exc}"

        bulk_error = None
        try:
            with create_session() as session:
                delete_seconds = delete_current(session)
                insert_seconds = sqlalchemy_insert(session)
                commit_started=perf_counter(); session.commit(); commit_seconds=perf_counter()-commit_started
            return {
                "successful_symbols": tuple(x.symbol for x in snapshots), "failed_symbols": {},
                "delete_seconds": round(delete_seconds,6), "prepare_seconds": round(prepare_seconds,6),
                "insert_seconds": round(insert_seconds,6), "commit_seconds": round(commit_seconds,6),
                "total_seconds": round(perf_counter()-total_started,6),
                "mode": "SQLALCHEMY_BULK_FALLBACK", "copy_used": False, "copy_error": copy_error,
                "summary_rows": len(summaries), "strike_rows": len(strikes),
                "expiration_rows": len(expirations), "surface_rows": len(surfaces),
            }
        except Exception as exc:
            bulk_error = f"{type(exc).__name__}: {exc}"

        successful=[]; failed={}; fallback_started=perf_counter()
        for snapshot in snapshots:
            try:
                with create_session() as session:
                    cls._persist(session, snapshot)
                successful.append(snapshot.symbol)
            except Exception as exc:
                failed[snapshot.symbol]=f"{type(exc).__name__}: {exc}"
        return {
            "successful_symbols": tuple(successful), "failed_symbols": failed,
            "delete_seconds": 0.0, "prepare_seconds": round(prepare_seconds,6),
            "insert_seconds": 0.0, "commit_seconds": 0.0,
            "total_seconds": round(perf_counter()-total_started,6),
            "fallback_seconds": round(perf_counter()-fallback_started,6),
            "mode": "SYMBOL_FALLBACK_AFTER_COPY_AND_BULK_FAILURE",
            "copy_error": copy_error, "bulk_error": bulk_error,
        }

    @staticmethod
    def _persist(session, snapshot):
        """Historical symbol-isolated writer retained as fail-safe fallback."""
        from .database_models import (
            DealerExpirationProfileModel,
            DealerPositionSnapshotModel,
            DealerStrikeProfileModel,
            IVSurfaceSnapshotModel,
        )

        total_started = perf_counter()
        ad = date.fromisoformat(snapshot.as_of_date)
        merge_started = perf_counter()
        session.merge(DealerPositionSnapshotModel.from_snapshot(snapshot))
        merge_seconds = perf_counter() - merge_started
        delete_started = perf_counter()
        for model in (DealerStrikeProfileModel, DealerExpirationProfileModel, IVSurfaceSnapshotModel):
            session.execute(delete(model).where(model.symbol == snapshot.symbol, model.as_of_date == ad))
        delete_seconds = perf_counter() - delete_started
        prepare_started = perf_counter()
        session.add_all(
            [DealerStrikeProfileModel(**InstitutionalMarketStructureService._strike_mapping(snapshot.symbol, ad, x)) for x in snapshot.strike_exposures]
        )
        session.add_all(
            [DealerExpirationProfileModel(**InstitutionalMarketStructureService._expiration_mapping(snapshot.symbol, ad, x)) for x in snapshot.expiration_exposures]
        )
        session.add_all(
            [IVSurfaceSnapshotModel(**InstitutionalMarketStructureService._surface_mapping(snapshot.symbol, ad, x)) for x in snapshot.iv_surface]
        )
        prepare_seconds = perf_counter() - prepare_started
        commit_started = perf_counter()
        session.commit()
        commit_seconds = perf_counter() - commit_started
        return {
            "merge_seconds": merge_seconds,
            "delete_seconds": delete_seconds,
            "prepare_seconds": prepare_seconds,
            "commit_seconds": commit_seconds,
            "total_seconds": perf_counter() - total_started,
        }
