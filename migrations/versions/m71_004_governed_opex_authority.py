"""M71.4 governed OPEX authority, settlement truth, and calibration lineage.

Revision ID: m71_004
Revises: m69_008
"""

from alembic import op
import sqlalchemy as sa


revision = "m71_004"
down_revision = "m69_008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "opex_forecast_snapshots",
        sa.Column("input_fingerprint", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_m714_opex_forecast_input_fingerprint",
        "opex_forecast_snapshots",
        ["input_fingerprint"],
    )
    op.create_index(
        "uq_m714_opex_forecast_input_fingerprint",
        "opex_forecast_snapshots",
        ["input_fingerprint"],
        unique=True,
        postgresql_where=sa.text("input_fingerprint IS NOT NULL"),
    )

    op.add_column(
        "opex_forecast_publications",
        sa.Column("authority_input_fingerprint", sa.String(64), nullable=True),
    )
    op.add_column(
        "opex_forecast_publications",
        sa.Column(
            "coverage_status",
            sa.String(32),
            nullable=False,
            server_default="UNKNOWN",
        ),
    )
    op.create_index(
        "ix_m714_opex_publication_authority_fingerprint",
        "opex_forecast_publications",
        ["authority_input_fingerprint"],
    )
    op.create_index(
        "ix_m714_opex_publication_coverage_status",
        "opex_forecast_publications",
        ["coverage_status"],
    )
    op.execute(
        """
        UPDATE opex_forecast_publications
        SET coverage_status = CASE
            WHEN forecast_count = jsonb_array_length(
                COALESCE(payload_json::jsonb -> 'forecast_ids', '[]'::jsonb)
            )
            THEN 'LEGACY_COUNT_MATCH'
            ELSE 'LEGACY_INCOMPLETE'
        END
        """
    )

    for column in (
        sa.Column("settlement_symbol", sa.String(32), nullable=True),
        sa.Column("settlement_style", sa.String(64), nullable=True),
        sa.Column("settlement_source", sa.String(96), nullable=True),
        sa.Column("sample_group_key", sa.String(160), nullable=True),
        sa.Column("horizon_bucket", sa.String(16), nullable=True),
    ):
        op.add_column("opex_forecast_outcomes", column)
    for name, column in (
        ("ix_m714_opex_outcome_settlement_symbol", "settlement_symbol"),
        ("ix_m714_opex_outcome_settlement_source", "settlement_source"),
        ("ix_m714_opex_outcome_sample_group", "sample_group_key"),
        ("ix_m714_opex_outcome_horizon", "horizon_bucket"),
    ):
        op.create_index(name, "opex_forecast_outcomes", [column])

    op.create_table(
        "opex_settlement_values",
        sa.Column("settlement_id", sa.String(128), primary_key=True),
        sa.Column("underlying_symbol", sa.String(16), nullable=False),
        sa.Column("expiration", sa.String(16), nullable=False),
        sa.Column("settlement_symbol", sa.String(32), nullable=False),
        sa.Column("settlement_style", sa.String(64), nullable=False),
        sa.Column("settlement_value", sa.Float(), nullable=False),
        sa.Column("settlement_source", sa.String(96), nullable=False),
        sa.Column("observed_at", sa.String(64), nullable=False),
        sa.Column("lineage_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "underlying_symbol",
            "expiration",
            name="uq_m714_opex_settlement_cycle",
        ),
    )
    for name, column in (
        ("ix_m714_opex_settlement_underlying", "underlying_symbol"),
        ("ix_m714_opex_settlement_expiration", "expiration"),
        ("ix_m714_opex_settlement_symbol", "settlement_symbol"),
        ("ix_m714_opex_settlement_source", "settlement_source"),
        ("ix_m714_opex_settlement_observed", "observed_at"),
    ):
        op.create_index(name, "opex_settlement_values", [column])


def downgrade() -> None:
    op.drop_table("opex_settlement_values")
    for name in (
        "ix_m714_opex_outcome_horizon",
        "ix_m714_opex_outcome_sample_group",
        "ix_m714_opex_outcome_settlement_source",
        "ix_m714_opex_outcome_settlement_symbol",
    ):
        op.drop_index(name, table_name="opex_forecast_outcomes")
    for column in (
        "horizon_bucket",
        "sample_group_key",
        "settlement_source",
        "settlement_style",
        "settlement_symbol",
    ):
        op.drop_column("opex_forecast_outcomes", column)
    op.drop_index(
        "ix_m714_opex_publication_coverage_status",
        table_name="opex_forecast_publications",
    )
    op.drop_index(
        "ix_m714_opex_publication_authority_fingerprint",
        table_name="opex_forecast_publications",
    )
    op.drop_column("opex_forecast_publications", "coverage_status")
    op.drop_column(
        "opex_forecast_publications",
        "authority_input_fingerprint",
    )
    op.drop_index(
        "uq_m714_opex_forecast_input_fingerprint",
        table_name="opex_forecast_snapshots",
    )
    op.drop_index(
        "ix_m714_opex_forecast_input_fingerprint",
        table_name="opex_forecast_snapshots",
    )
    op.drop_column("opex_forecast_snapshots", "input_fingerprint")
