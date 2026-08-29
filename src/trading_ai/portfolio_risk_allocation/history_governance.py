from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

from sqlalchemy import text


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class M64DecisionHistoryPurgeService:
    """Governed PostgreSQL recovery and bounded retention for M64 decisions.

    The explicit recovery path preserves every authoritative or operationally
    referenced decision, copies those rows into a transaction-local table,
    truncates the defective relation, and restores the protected rows before
    commit. PostgreSQL TRUNCATE is transactional, and inbound foreign keys are
    a hard stop. CASCADE is deliberately forbidden.
    """

    TABLE_NAME = "portfolio_decision_intelligence_snapshots"
    PROTECTED_REASONS_TABLE = "m64_2_4_3_protected_decision_reasons"
    PROTECTED_ROWS_TABLE = "m64_2_4_3_protected_decision_rows"
    CONFIRMATION_TOKEN = "PURGE-KNOWN-INVALID-M64-HISTORY"
    LOGICAL_REFERENCE_COLUMNS = {
        "decision_intelligence_id",
        "portfolio_decision_id",
    }
    OPERATIONAL_TABLES = (
        "managed_positions",
        "execution_intents",
        "advanced_trade_plans",
    )
    LOCK_TIMEOUT_MS = 30_000
    PURGE_STATEMENT_TIMEOUT_MS = 900_000
    RETENTION_STATEMENT_TIMEOUT_MS = 30_000
    RETENTION_DAYS = 7
    RETENTION_BATCH_SIZE = 10_000
    FORENSIC_BOUNDARY_SAMPLE_SIZE = 25
    MAX_MANIFEST_PROTECTED_ID_SAMPLE = 100

    def __init__(self, session_factory):
        self.session_factory = session_factory

    @staticmethod
    def _quote(identifier: str) -> str:
        return '"' + str(identifier).replace('"', '""') + '"'

    @staticmethod
    def _emit(progress, stage: str, **details) -> None:
        if progress:
            progress(stage, details)

    def _schema_inventory(self, session) -> tuple[str, dict[str, set[str]]]:
        schema = str(session.scalar(text("SELECT current_schema()")) or "public")
        rows = session.execute(text("""
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = :schema
            ORDER BY table_name, ordinal_position
        """), {"schema": schema}).mappings().all()
        inventory: dict[str, set[str]] = {}
        for row in rows:
            inventory.setdefault(str(row["table_name"]), set()).add(
                str(row["column_name"])
            )
        return schema, inventory

    def _qualified_source(self, schema: str) -> str:
        return f"{self._quote(schema)}.{self._quote(self.TABLE_NAME)}"

    def _create_protected_reasons(
        self,
        session,
        *,
        schema: str,
        inventory: dict[str, set[str]],
        portfolio_id: str,
        target_risk_snapshot_id: str | None,
        include_forensic_samples: bool,
    ) -> None:
        source = self._qualified_source(schema)
        protected = self._quote(self.PROTECTED_REASONS_TABLE)
        session.execute(text(f"""
            CREATE TEMP TABLE {protected} (
                decision_intelligence_id varchar(128) NOT NULL,
                reason text NOT NULL,
                PRIMARY KEY (decision_intelligence_id, reason)
            ) ON COMMIT DROP
        """))

        def protect(select_sql: str, parameters: dict) -> None:
            session.execute(text(f"""
                INSERT INTO {protected} (decision_intelligence_id, reason)
                {select_sql}
                ON CONFLICT DO NOTHING
            """), parameters)

        protect(
            f"""
                SELECT decision_intelligence_id, 'OTHER_PORTFOLIO'
                FROM {source}
                WHERE portfolio_id <> :portfolio_id
            """,
            {"portfolio_id": portfolio_id},
        )
        protect(
            f"""
                SELECT decision.decision_intelligence_id, 'PUBLISHED_RISK'
                FROM {source} AS decision
                JOIN {self._quote(schema)}.{self._quote('portfolio_allocation_publications')}
                    AS publication
                  ON publication.portfolio_id = decision.portfolio_id
                 AND publication.risk_snapshot_id = decision.risk_snapshot_id
                WHERE decision.portfolio_id = :portfolio_id
            """,
            {"portfolio_id": portfolio_id},
        )
        if target_risk_snapshot_id:
            protect(
                f"""
                    SELECT decision_intelligence_id, 'PINNED_RECOVERY_RISK'
                    FROM {source}
                    WHERE portfolio_id = :portfolio_id
                      AND risk_snapshot_id = :target_risk_snapshot_id
                """,
                {
                    "portfolio_id": portfolio_id,
                    "target_risk_snapshot_id": target_risk_snapshot_id,
                },
            )

        for table_name, columns in sorted(inventory.items()):
            if table_name == self.TABLE_NAME:
                continue
            for column_name in sorted(columns & self.LOGICAL_REFERENCE_COLUMNS):
                reason = f"DIRECT_REFERENCE:{table_name}.{column_name}"
                referenced = (
                    f"{self._quote(schema)}.{self._quote(table_name)}"
                )
                protect(
                    f"""
                        SELECT decision.decision_intelligence_id, :reason
                        FROM {source} AS decision
                        JOIN {referenced} AS reference
                          ON CAST(reference.{self._quote(column_name)} AS text)
                           = decision.decision_intelligence_id
                        WHERE decision.portfolio_id = :portfolio_id
                    """,
                    {"portfolio_id": portfolio_id, "reason": reason},
                )

        for table_name in self.OPERATIONAL_TABLES:
            columns = inventory.get(table_name, set())
            if "opportunity_id" not in columns:
                continue
            operational = f"{self._quote(schema)}.{self._quote(table_name)}"
            portfolio_predicate = (
                "WHERE portfolio_id = :portfolio_id"
                if "portfolio_id" in columns
                else "WHERE opportunity_id IS NOT NULL"
            )
            protect(
                f"""
                    SELECT chosen.decision_intelligence_id,
                           :reason
                    FROM (
                        SELECT DISTINCT opportunity_id
                        FROM {operational}
                        {portfolio_predicate}
                          AND opportunity_id IS NOT NULL
                    ) AS operational_opportunity
                    JOIN LATERAL (
                        SELECT decision.decision_intelligence_id
                        FROM {source} AS decision
                        WHERE decision.portfolio_id = :portfolio_id
                          AND decision.opportunity_id =
                              operational_opportunity.opportunity_id
                        ORDER BY decision.created_at DESC,
                                 decision.decision_intelligence_id DESC
                        LIMIT 1
                    ) AS chosen ON TRUE
                """,
                {
                    "portfolio_id": portfolio_id,
                    "reason": f"OPERATIONAL_OPPORTUNITY_LATEST:{table_name}",
                },
            )

        if include_forensic_samples:
            protect(
                f"""
                    (
                        SELECT decision_intelligence_id,
                               'FORENSIC_BOUNDARY_SAMPLE:FIRST'
                        FROM {source}
                        WHERE portfolio_id = :portfolio_id
                        ORDER BY decision_intelligence_id ASC
                        LIMIT :sample_size
                    )
                    UNION ALL
                    (
                        SELECT decision_intelligence_id,
                               'FORENSIC_BOUNDARY_SAMPLE:LAST'
                        FROM {source}
                        WHERE portfolio_id = :portfolio_id
                        ORDER BY decision_intelligence_id DESC
                        LIMIT :sample_size
                    )
                """,
                {
                    "portfolio_id": portfolio_id,
                    "sample_size": self.FORENSIC_BOUNDARY_SAMPLE_SIZE,
                },
            )

    def _protected_manifest(self, session) -> dict:
        protected = self._quote(self.PROTECTED_REASONS_TABLE)
        protected_count = int(session.scalar(text(f"""
            SELECT COUNT(DISTINCT decision_intelligence_id)
            FROM {protected}
        """)) or 0)
        reason_counts = {
            str(row["reason"]): int(row["protected_count"])
            for row in session.execute(text(f"""
                SELECT reason, COUNT(*) AS protected_count
                FROM {protected}
                GROUP BY reason
                ORDER BY reason
            """)).mappings().all()
        }
        digest = sha256()
        sample: list[str] = []
        result = session.execute(text(f"""
            SELECT DISTINCT decision_intelligence_id
            FROM {protected}
            ORDER BY decision_intelligence_id
        """))
        if hasattr(result, "yield_per"):
            result = result.yield_per(1_000)
        for row in result:
            decision_id = str(row[0])
            digest.update(decision_id.encode())
            digest.update(b"\n")
            if len(sample) < self.MAX_MANIFEST_PROTECTED_ID_SAMPLE:
                sample.append(decision_id)
        return {
            "protected_count": protected_count,
            "protected_reason_counts": reason_counts,
            "protected_id_sha256": digest.hexdigest(),
            "protected_id_sample": sample,
            "protected_id_sample_truncated": protected_count > len(sample),
        }

    def purge_known_invalid_history(
        self,
        portfolio_id: str,
        *,
        target_risk_snapshot_id: str | None,
        confirmation_token: str,
        dry_run: bool = False,
        progress=None,
    ) -> dict:
        if confirmation_token != self.CONFIRMATION_TOKEN:
            raise PermissionError(
                "Governed M64 historical purge confirmation token is missing or invalid"
            )
        if not target_risk_snapshot_id:
            raise ValueError(
                "Governed M64 historical purge requires a pinned risk snapshot"
            )

        purge_id = "M64-PURGE-" + sha256(
            f"{portfolio_id}:{utc_now()}".encode()
        ).hexdigest()[:32].upper()
        started_at = utc_now()
        self._emit(
            progress,
            "invalid_history_purge_requested",
            purge_id=purge_id,
            portfolio_id=portfolio_id,
            target_risk_snapshot_id=target_risk_snapshot_id,
        )

        with self.session_factory() as session:
            dialect_name = (
                session.bind.dialect.name
                if session.bind is not None
                else "unknown"
            )
            if dialect_name != "postgresql":
                raise RuntimeError(
                    "M64 governed historical purge requires PostgreSQL"
                )
            schema, inventory = self._schema_inventory(session)
            if self.TABLE_NAME not in inventory:
                raise RuntimeError(
                    f"Required table {self.TABLE_NAME} does not exist"
                )
            if "portfolio_allocation_publications" not in inventory:
                raise RuntimeError(
                    "Required M64 publication table does not exist"
                )
            if "portfolio_risk_allocation_snapshots" not in inventory:
                raise RuntimeError(
                    "Required M64 risk snapshot table does not exist"
                )
            source = self._qualified_source(schema)
            qualified_name = f"{schema}.{self.TABLE_NAME}"

            target_risk = session.execute(text(f"""
                SELECT
                    snapshot_id,
                    status,
                    net_liquidation,
                    buying_power,
                    payload_json::jsonb #>>
                        '{{capital,trading_risk_basis}}' AS trading_risk_basis
                FROM {self._quote(schema)}.{self._quote('portfolio_risk_allocation_snapshots')}
                WHERE portfolio_id = :portfolio_id
                  AND snapshot_id = :target_risk_snapshot_id
            """), {
                "portfolio_id": portfolio_id,
                "target_risk_snapshot_id": target_risk_snapshot_id,
            }).mappings().first()
            if target_risk is None:
                raise RuntimeError(
                    "Pinned M64 recovery risk snapshot does not exist for "
                    f"{portfolio_id}: {target_risk_snapshot_id}"
                )
            target_risk_validation = dict(target_risk)
            if (
                str(target_risk_validation.get("status") or "").upper()
                != "READY"
                or float(target_risk_validation.get("net_liquidation") or 0)
                <= 0
                or float(target_risk_validation.get("buying_power") or 0) <= 0
                or target_risk_validation.get("trading_risk_basis")
                != "GOVERNED_PRE_EXPIRATION_DEFINED_LOSS"
            ):
                raise RuntimeError(
                    "Pinned M64 recovery risk snapshot failed governed READY "
                    "capital validation: "
                    + json.dumps(target_risk_validation, sort_keys=True, default=str)
                )

            inbound_foreign_keys = [
                dict(row)
                for row in session.execute(text("""
                    SELECT
                        constraint_row.conname AS constraint_name,
                        constraint_row.conrelid::regclass::text
                            AS referencing_table
                    FROM pg_constraint AS constraint_row
                    WHERE constraint_row.contype = 'f'
                      AND constraint_row.confrelid =
                          to_regclass(:qualified_name)
                    ORDER BY referencing_table, constraint_name
                """), {
                    "qualified_name": qualified_name,
                }).mappings().all()
            ]
            if inbound_foreign_keys:
                raise RuntimeError(
                    "M64 purge refused because inbound foreign keys exist: "
                    + json.dumps(inbound_foreign_keys, sort_keys=True)
                )

            publication = session.execute(text(f"""
                SELECT
                    publication_id,
                    risk_snapshot_id,
                    optimization_snapshot_id,
                    published_at,
                    status
                FROM {self._quote(schema)}.{self._quote('portfolio_allocation_publications')}
                WHERE portfolio_id = :portfolio_id
                  AND publication_name = 'current_portfolio_allocation'
            """), {"portfolio_id": portfolio_id}).mappings().first()
            if publication is None:
                raise RuntimeError(
                    f"No current M64 publication exists for {portfolio_id}"
                )
            publication_before = dict(publication)

            session.execute(text(
                f"SET LOCAL lock_timeout = '{self.LOCK_TIMEOUT_MS}ms'"
            ))
            session.execute(text(
                f"SET LOCAL statement_timeout = "
                f"'{self.PURGE_STATEMENT_TIMEOUT_MS}ms'"
            ))
            session.execute(text(f"LOCK TABLE {source} IN SHARE MODE"))

            source_stats = dict(session.execute(text(f"""
                SELECT
                    COUNT(*) AS total_rows,
                    COUNT(*) FILTER (
                        WHERE portfolio_id = :portfolio_id
                    ) AS portfolio_rows,
                    COUNT(*) FILTER (
                        WHERE portfolio_id <> :portfolio_id
                    ) AS other_portfolio_rows,
                    MIN(created_at) FILTER (
                        WHERE portfolio_id = :portfolio_id
                    ) AS earliest_created_at,
                    MAX(created_at) FILTER (
                        WHERE portfolio_id = :portfolio_id
                    ) AS latest_created_at,
                    MIN(decision_intelligence_id) FILTER (
                        WHERE portfolio_id = :portfolio_id
                    ) AS first_decision_id,
                    MAX(decision_intelligence_id) FILTER (
                        WHERE portfolio_id = :portfolio_id
                    ) AS last_decision_id
                FROM {source}
            """), {"portfolio_id": portfolio_id}).mappings().one())
            source_size_bytes = int(session.scalar(text(
                "SELECT pg_total_relation_size(to_regclass(:qualified_name))"
            ), {"qualified_name": qualified_name}) or 0)

            self._create_protected_reasons(
                session,
                schema=schema,
                inventory=inventory,
                portfolio_id=portfolio_id,
                target_risk_snapshot_id=target_risk_snapshot_id,
                include_forensic_samples=True,
            )
            protected_manifest = self._protected_manifest(session)
            protected = self._quote(self.PROTECTED_REASONS_TABLE)
            protected_rows = self._quote(self.PROTECTED_ROWS_TABLE)
            session.execute(text(f"""
                CREATE TEMP TABLE {protected_rows} ON COMMIT DROP AS
                SELECT decision.*
                FROM {source} AS decision
                JOIN (
                    SELECT DISTINCT decision_intelligence_id
                    FROM {protected}
                ) AS protected_id
                  ON protected_id.decision_intelligence_id =
                     decision.decision_intelligence_id
            """))
            copied_count = int(session.scalar(text(f"""
                SELECT COUNT(*) FROM {protected_rows}
            """)) or 0)
            if copied_count != protected_manifest["protected_count"]:
                raise RuntimeError(
                    "Protected-row copy validation failed: "
                    f"expected={protected_manifest['protected_count']}, "
                    f"copied={copied_count}"
                )
            purge_count = int(source_stats["total_rows"] or 0) - copied_count
            if purge_count < 0:
                raise RuntimeError("Protected rows exceed source rows")

            preflight = {
                "version": "M64.2.4.3-GOVERNED-PURGE-MANIFEST-1.0",
                "purge_id": purge_id,
                "status": "PREFLIGHT_VALIDATED",
                "portfolio_id": portfolio_id,
                "started_at": started_at,
                "target_risk_snapshot_id": target_risk_snapshot_id,
                "target_risk_validation": target_risk_validation,
                "publication_before": publication_before,
                "source_stats": source_stats,
                "source_size_bytes": source_size_bytes,
                **protected_manifest,
                "eligible_for_purge": purge_count,
                "inbound_foreign_keys": inbound_foreign_keys,
                "destructive_strategy": (
                    "TRANSACTIONAL_TRUNCATE_AND_PROTECTED_ROW_REINSERT"
                ),
                "cascade_used": False,
            }
            self._emit(progress, "invalid_history_purge_preflight_validated", **preflight)
            if dry_run:
                session.rollback()
                preview = {
                    **preflight,
                    "status": "DRY_RUN_COMPLETE",
                    "would_purge_rows": purge_count,
                    "database_mutated": False,
                }
                preview["manifest_sha256"] = sha256(
                    json.dumps(preview, sort_keys=True, default=str).encode()
                ).hexdigest()
                self._emit(
                    progress,
                    "invalid_history_purge_dry_run_completed",
                    **preview,
                )
                return preview

            # TRUNCATE takes ACCESS EXCLUSIVE only for the short destructive
            # section. It is transactional in PostgreSQL; any subsequent error
            # restores the original relation automatically.
            session.execute(text(f"TRUNCATE TABLE {source}"))
            session.execute(text(f"""
                INSERT INTO {source}
                SELECT * FROM {protected_rows}
            """))
            after_stats = dict(session.execute(text(f"""
                SELECT
                    COUNT(*) AS total_rows,
                    COUNT(*) FILTER (
                        WHERE portfolio_id = :portfolio_id
                    ) AS portfolio_rows,
                    COUNT(*) FILTER (
                        WHERE portfolio_id <> :portfolio_id
                    ) AS other_portfolio_rows,
                    COUNT(*) FILTER (
                        WHERE portfolio_id = :portfolio_id
                          AND risk_snapshot_id = :published_risk_snapshot_id
                    ) AS published_risk_rows,
                    COUNT(*) FILTER (
                        WHERE portfolio_id = :portfolio_id
                          AND risk_snapshot_id = :target_risk_snapshot_id
                    ) AS target_risk_rows
                FROM {source}
            """), {
                "portfolio_id": portfolio_id,
                "published_risk_snapshot_id":
                    publication_before["risk_snapshot_id"],
                "target_risk_snapshot_id": target_risk_snapshot_id,
            }).mappings().one())
            if int(after_stats["total_rows"] or 0) != copied_count:
                raise RuntimeError(
                    "Post-purge total-row validation failed: "
                    f"expected={copied_count}, "
                    f"observed={after_stats['total_rows']}"
                )
            if int(after_stats["other_portfolio_rows"] or 0) != int(
                source_stats["other_portfolio_rows"] or 0
            ):
                raise RuntimeError(
                    "Post-purge other-portfolio preservation validation failed"
                )
            publication_after = session.execute(text(f"""
                SELECT
                    publication_id,
                    risk_snapshot_id,
                    optimization_snapshot_id,
                    published_at,
                    status
                FROM {self._quote(schema)}.{self._quote('portfolio_allocation_publications')}
                WHERE portfolio_id = :portfolio_id
                  AND publication_name = 'current_portfolio_allocation'
            """), {"portfolio_id": portfolio_id}).mappings().one()
            if dict(publication_after) != publication_before:
                raise RuntimeError(
                    "Current publication changed during governed purge"
                )
            session.execute(text(f"ANALYZE {source}"))
            retained_size_bytes = int(session.scalar(text(
                "SELECT pg_total_relation_size(to_regclass(:qualified_name))"
            ), {"qualified_name": qualified_name}) or 0)
            session.commit()

        manifest = {
            **preflight,
            "status": "COMMITTED",
            "completed_at": utc_now(),
            "purged_rows": purge_count,
            "retained_rows": copied_count,
            "retained_size_bytes": retained_size_bytes,
            "estimated_reclaimed_bytes": max(
                0,
                source_size_bytes - retained_size_bytes,
            ),
            "after_stats": after_stats,
            "publication_after": dict(publication_after),
            "transactional_rollback_guarantee": True,
        }
        manifest["manifest_sha256"] = sha256(
            json.dumps(manifest, sort_keys=True, default=str).encode()
        ).hexdigest()
        self._emit(progress, "invalid_history_purge_committed", **manifest)
        return manifest

    def prune_expired_history(
        self,
        portfolio_id: str,
        *,
        progress=None,
    ) -> dict:
        """Delete one bounded batch of expired, unreferenced superseded rows."""
        with self.session_factory() as session:
            dialect_name = (
                session.bind.dialect.name
                if session.bind is not None
                else "unknown"
            )
            if dialect_name != "postgresql":
                return {
                    "status": "SKIPPED_NON_POSTGRESQL",
                    "pruned": 0,
                }
            schema, inventory = self._schema_inventory(session)
            if self.TABLE_NAME not in inventory:
                return {"status": "SKIPPED_TABLE_MISSING", "pruned": 0}
            source = self._qualified_source(schema)
            session.execute(text(
                f"SET LOCAL lock_timeout = '{self.LOCK_TIMEOUT_MS}ms'"
            ))
            session.execute(text(
                f"SET LOCAL statement_timeout = "
                f"'{self.RETENTION_STATEMENT_TIMEOUT_MS}ms'"
            ))
            self._create_protected_reasons(
                session,
                schema=schema,
                inventory=inventory,
                portfolio_id=portfolio_id,
                target_risk_snapshot_id=None,
                include_forensic_samples=True,
            )
            protected = self._quote(self.PROTECTED_REASONS_TABLE)
            cutoff = (
                datetime.now(timezone.utc) - timedelta(days=self.RETENTION_DAYS)
            ).isoformat()
            rows = session.execute(text(f"""
                WITH candidates AS (
                    SELECT decision.ctid
                    FROM {source} AS decision
                    LEFT JOIN (
                        SELECT DISTINCT decision_intelligence_id
                        FROM {protected}
                    ) AS protected_id
                      ON protected_id.decision_intelligence_id =
                         decision.decision_intelligence_id
                    WHERE decision.portfolio_id = :portfolio_id
                      AND protected_id.decision_intelligence_id IS NULL
                      AND COALESCE(
                            decision.payload_json::jsonb
                                #>> '{{lifecycle,status}}',
                            ''
                          ) = 'SUPERSEDED'
                      AND decision.created_at < :cutoff
                    ORDER BY decision.created_at,
                             decision.decision_intelligence_id
                    LIMIT :batch_size
                    FOR UPDATE OF decision SKIP LOCKED
                )
                DELETE FROM {source} AS decision
                USING candidates
                WHERE decision.ctid = candidates.ctid
                RETURNING decision.decision_intelligence_id
            """), {
                "portfolio_id": portfolio_id,
                "cutoff": cutoff,
                "batch_size": self.RETENTION_BATCH_SIZE,
            }).all()
            pruned = len(rows)
            session.commit()
        result = {
            "status": "COMPLETE_BATCH",
            "pruned": pruned,
            "retention_days": self.RETENTION_DAYS,
            "batch_size": self.RETENTION_BATCH_SIZE,
            "cutoff": cutoff,
            "policy": "PUBLISHED_REFERENCED_OPERATIONAL_AND_FORENSIC_PRESERVATION",
        }
        self._emit(progress, "historical_retention_batch_completed", **result)
        return result
