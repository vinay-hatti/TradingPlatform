"""M68.2 governed directional Inflection authority and semantic timeline.

Revision ID: m68_002
Revises: m71_004
"""

from alembic import op
import sqlalchemy as sa


revision = "m68_002"
down_revision = "m71_004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    snapshot_columns = (
        sa.Column("directional_score", sa.Float(), nullable=True),
        sa.Column("signal_strength", sa.Float(), nullable=True),
        sa.Column("input_quality", sa.Float(), nullable=True),
        sa.Column("disposition", sa.String(32), nullable=True),
        sa.Column("input_fingerprint", sa.String(64), nullable=True),
        sa.Column("semantic_state_hash", sa.String(64), nullable=True),
        sa.Column("source_as_of_date", sa.String(16), nullable=True),
        sa.Column("option_snapshot_id", sa.String(128), nullable=True),
        sa.Column("dealer_as_of_date", sa.String(16), nullable=True),
        sa.Column("coverage_status", sa.String(32), nullable=True),
    )
    for column in snapshot_columns:
        op.add_column("institutional_inflection_snapshots", column)
    op.execute("""
        UPDATE institutional_inflection_snapshots
           SET directional_score = CASE
                 WHEN direction = 'BEARISH' THEN -ABS(inflection_score)
                 WHEN direction = 'BULLISH' THEN ABS(inflection_score)
                 ELSE 0
               END,
               signal_strength = ABS(inflection_score),
               input_quality = 0,
               disposition = 'ABSTAIN',
               input_fingerprint = md5('legacy-input:' || snapshot_id),
               semantic_state_hash = md5('legacy-semantic:' || state_hash),
               source_as_of_date = COALESCE(
                   payload_json::jsonb #>> '{lineage,source_as_of_date}',
                   LEFT(snapshot_timestamp, 10)
               ),
               option_snapshot_id = payload_json::jsonb #>>
                   '{lineage,option_snapshot_id}',
               dealer_as_of_date = payload_json::jsonb #>>
                   '{lineage,dealer_as_of_date}',
               coverage_status = 'LEGACY_UNVERIFIED'
    """)
    for column in (
        "directional_score", "signal_strength", "input_quality", "disposition",
        "input_fingerprint", "semantic_state_hash", "source_as_of_date",
        "coverage_status",
    ):
        op.alter_column(
            "institutional_inflection_snapshots", column, nullable=False
        )
    for name, column in (
        ("ix_m682_inflection_directional_score", "directional_score"),
        ("ix_m682_inflection_signal_strength", "signal_strength"),
        ("ix_m682_inflection_disposition", "disposition"),
        ("ix_m682_inflection_input_fingerprint", "input_fingerprint"),
        ("ix_m682_inflection_semantic_hash", "semantic_state_hash"),
        ("ix_m682_inflection_source_as_of", "source_as_of_date"),
        ("ix_m682_inflection_option_snapshot", "option_snapshot_id"),
        ("ix_m682_inflection_dealer_as_of", "dealer_as_of_date"),
        ("ix_m682_inflection_coverage", "coverage_status"),
    ):
        op.create_index(name, "institutional_inflection_snapshots", [column])

    op.drop_constraint(
        "uq_m68_timeline_state",
        "institutional_inflection_timeline_events",
        type_="unique",
    )
    timeline_columns = (
        sa.Column("source_run_id", sa.String(128), nullable=True),
        sa.Column("previous_transition_state", sa.String(64), nullable=True),
        sa.Column("transition_reason", sa.String(128), nullable=True),
        sa.Column("directional_score", sa.Float(), nullable=True),
        sa.Column("signal_strength", sa.Float(), nullable=True),
        sa.Column("semantic_state_hash", sa.String(64), nullable=True),
        sa.Column("event_fingerprint", sa.String(64), nullable=True),
    )
    for column in timeline_columns:
        op.add_column("institutional_inflection_timeline_events", column)
    op.execute("""
        UPDATE institutional_inflection_timeline_events
           SET source_run_id = COALESCE(
                   payload_json::jsonb #>> '{lineage,stock_scanner_run_id}',
                   'LEGACY'
               ),
               transition_reason = 'LEGACY_MATERIALIZATION',
               directional_score = CASE
                 WHEN payload_json::jsonb ->> 'direction' = 'BEARISH'
                   THEN -ABS(inflection_score)
                 WHEN payload_json::jsonb ->> 'direction' = 'BULLISH'
                   THEN ABS(inflection_score)
                 ELSE 0
               END,
               signal_strength = ABS(inflection_score),
               semantic_state_hash = md5('legacy-semantic:' || state_hash),
               event_fingerprint = md5('legacy-event:' || event_id)
    """)
    for column in (
        "source_run_id", "transition_reason", "directional_score",
        "signal_strength", "semantic_state_hash", "event_fingerprint",
    ):
        op.alter_column(
            "institutional_inflection_timeline_events", column, nullable=False
        )
    op.create_unique_constraint(
        "uq_m68_timeline_event_fingerprint",
        "institutional_inflection_timeline_events",
        ["event_fingerprint"],
    )
    for name, column in (
        ("ix_m682_timeline_source_run", "source_run_id"),
        ("ix_m682_timeline_previous_state", "previous_transition_state"),
        ("ix_m682_timeline_semantic_hash", "semantic_state_hash"),
    ):
        op.create_index(
            name, "institutional_inflection_timeline_events", [column]
        )

    publication_columns = (
        sa.Column("authority_input_fingerprint", sa.String(64), nullable=True),
        sa.Column(
            "coverage_status", sa.String(32), nullable=False,
            server_default="LEGACY_UNVERIFIED",
        ),
        sa.Column("source_as_of_date", sa.String(16), nullable=True),
        sa.Column("option_snapshot_id", sa.String(128), nullable=True),
    )
    for column in publication_columns:
        op.add_column("institutional_inflection_publications", column)
    for name, column in (
        ("ix_m682_publication_fingerprint", "authority_input_fingerprint"),
        ("ix_m682_publication_coverage", "coverage_status"),
        ("ix_m682_publication_source_as_of", "source_as_of_date"),
        ("ix_m682_publication_option_snapshot", "option_snapshot_id"),
    ):
        op.create_index(name, "institutional_inflection_publications", [column])


def downgrade() -> None:
    for name in (
        "ix_m682_publication_option_snapshot",
        "ix_m682_publication_source_as_of",
        "ix_m682_publication_coverage",
        "ix_m682_publication_fingerprint",
    ):
        op.drop_index(name, table_name="institutional_inflection_publications")
    for column in (
        "option_snapshot_id", "source_as_of_date", "coverage_status",
        "authority_input_fingerprint",
    ):
        op.drop_column("institutional_inflection_publications", column)

    for name in (
        "ix_m682_timeline_semantic_hash",
        "ix_m682_timeline_previous_state",
        "ix_m682_timeline_source_run",
    ):
        op.drop_index(name, table_name="institutional_inflection_timeline_events")
    op.drop_constraint(
        "uq_m68_timeline_event_fingerprint",
        "institutional_inflection_timeline_events",
        type_="unique",
    )
    for column in (
        "event_fingerprint", "semantic_state_hash", "signal_strength",
        "directional_score", "transition_reason", "previous_transition_state",
        "source_run_id",
    ):
        op.drop_column("institutional_inflection_timeline_events", column)
    op.create_unique_constraint(
        "uq_m68_timeline_state",
        "institutional_inflection_timeline_events",
        ["symbol", "timeframe", "state_hash"],
    )

    for name in (
        "ix_m682_inflection_coverage", "ix_m682_inflection_dealer_as_of",
        "ix_m682_inflection_option_snapshot", "ix_m682_inflection_source_as_of",
        "ix_m682_inflection_semantic_hash", "ix_m682_inflection_input_fingerprint",
        "ix_m682_inflection_disposition", "ix_m682_inflection_signal_strength",
        "ix_m682_inflection_directional_score",
    ):
        op.drop_index(name, table_name="institutional_inflection_snapshots")
    for column in (
        "coverage_status", "dealer_as_of_date", "option_snapshot_id",
        "source_as_of_date", "semantic_state_hash", "input_fingerprint",
        "disposition", "input_quality", "signal_strength", "directional_score",
    ):
        op.drop_column("institutional_inflection_snapshots", column)
