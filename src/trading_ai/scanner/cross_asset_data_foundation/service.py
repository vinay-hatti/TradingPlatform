from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .contracts import (
    CrossAssetGovernanceStatus,
    CrossAssetRunProfile,
    CrossAssetUniverseMember,
)
from .engine import CrossAssetFeatureEngine
from .policy import CrossAssetFeaturePolicy
from .serialization import write_jsonl_atomic
from .universe import default_cross_asset_universe


def _resolve_database_engine() -> Engine:
    """Resolve the platform's configured SQLAlchemy engine.

    Milestone packages must not assume one historical database-module layout.
    The TradingPlatform repository has used package exports and dedicated
    engine/session modules across milestones, so resolution is intentionally
    compatible with each supported layout.
    """

    candidates = (
        ("trading_ai.database", "engine"),
        ("trading_ai.database.engine", "engine"),
        ("trading_ai.database.session", "engine"),
        ("trading_ai.database.connection", "engine"),
        ("trading_ai.database.db", "engine"),
        ("database.database", "engine"),
    )

    failures: list[str] = []

    for module_name, attribute_name in candidates:
        try:
            module = import_module(module_name)
        except ModuleNotFoundError as exc:
            failures.append(f"{module_name}: {exc}")
            continue

        candidate = getattr(module, attribute_name, None)
        if candidate is None:
            failures.append(
                f"{module_name}: missing attribute {attribute_name!r}"
            )
            continue

        if isinstance(candidate, Engine):
            return candidate

        # SQLAlchemy Engine-like compatibility for wrapped/proxied engines.
        if hasattr(candidate, "connect") and callable(candidate.connect):
            return candidate

        failures.append(
            f"{module_name}.{attribute_name}: object has no connect()"
        )

    joined = "\n  - ".join(failures)
    raise RuntimeError(
        "Unable to locate the configured SQLAlchemy engine. "
        "Expected the project database package to export `engine`, or to "
        "provide it from database.engine/session/connection/db. "
        "Resolution attempts:\n  - "
        + joined
    )


class CrossAssetFeatureService:
    def __init__(
        self,
        policy: CrossAssetFeaturePolicy | None = None,
        universe: tuple[CrossAssetUniverseMember, ...] | None = None,
        database_engine: Engine | None = None,
    ) -> None:
        self.policy = policy or CrossAssetFeaturePolicy()
        self.universe = universe or default_cross_asset_universe()
        self.feature_engine = CrossAssetFeatureEngine(self.policy)
        self.database_engine = database_engine

    def run(
        self,
        *,
        as_of_date: date,
        output_path: str | Path,
    ) -> CrossAssetRunProfile:
        enabled_members = tuple(
            member for member in self.universe if member.enabled
        )
        symbols = sorted(
            {member.symbol for member in enabled_members}
            | {
                member.benchmark_symbol
                for member in enabled_members
                if member.benchmark_symbol
            }
        )

        rows_by_symbol = self._load_price_history(
            symbols=symbols,
            as_of_date=as_of_date,
        )

        profiles = tuple(
            self.feature_engine.evaluate(
                member=member,
                as_of_date=as_of_date,
                rows=rows_by_symbol.get(member.symbol, ()),
                benchmark_rows=(
                    rows_by_symbol.get(member.benchmark_symbol, ())
                    if member.benchmark_symbol
                    else None
                ),
            )
            for member in enabled_members
        )

        write_jsonl_atomic(output_path, profiles)

        return CrossAssetRunProfile(
            as_of_date=as_of_date,
            generated_at=datetime.now(timezone.utc),
            source_table="price_history",
            output_path=str(output_path),
            universe_size=len(enabled_members),
            symbols_read=sum(
                bool(rows_by_symbol.get(member.symbol))
                for member in enabled_members
            ),
            symbols_generated=len(profiles),
            ready_count=sum(
                profile.governance_status
                == CrossAssetGovernanceStatus.READY
                for profile in profiles
            ),
            review_count=sum(
                profile.governance_status
                == CrossAssetGovernanceStatus.REVIEW
                for profile in profiles
            ),
            excluded_count=sum(
                profile.governance_status
                == CrossAssetGovernanceStatus.EXCLUDED
                for profile in profiles
            ),
            metadata={
                "policy": self.policy.__dict__.copy(),
                "symbols_requested": symbols,
                "feature_version": "m35.phase5.step1.v1",
                "database_engine_module": (
                    self._engine().__class__.__module__
                ),
            },
        )

    def _engine(self) -> Engine:
        if self.database_engine is None:
            self.database_engine = _resolve_database_engine()
        return self.database_engine

    def _load_price_history(
        self,
        *,
        symbols: list[str],
        as_of_date: date,
    ) -> dict[str, list[dict[str, Any]]]:
        if not symbols:
            return {}

        query = text(
            """
            SELECT
                symbol,
                date,
                open,
                high,
                low,
                close,
                volume
            FROM price_history
            WHERE symbol = ANY(:symbols)
              AND date <= :as_of_date
            ORDER BY symbol, date
            """
        )

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

        with self._engine().connect() as connection:
            result = connection.execute(
                query,
                {
                    "symbols": symbols,
                    "as_of_date": as_of_date,
                },
            )
            for row in result.mappings():
                symbol = str(row["symbol"]).strip().upper()
                grouped[symbol].append(dict(row))

        return dict(grouped)
