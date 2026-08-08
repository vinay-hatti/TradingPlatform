"""Milestone 61 structured level and zone timeframe confluence.

Revision ID: m61_009
Revises: m61_008
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "m61_009"
down_revision = "m61_008"
branch_labels = None
depends_on = None

_TABLES = ("stock_support_resistance_levels", "stock_supply_demand_zones")


def upgrade():
    for table in _TABLES:
        op.alter_column(table, "timeframe", existing_type=sa.String(16), type_=sa.String(32), existing_nullable=False)
        op.add_column(table, sa.Column("primary_timeframe", sa.String(16), nullable=True))
        op.add_column(table, sa.Column("contributing_timeframes", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
        op.execute(sa.text(f"""
            UPDATE {table}
               SET primary_timeframe = split_part(timeframe, ',', 1),
                   contributing_timeframes = COALESCE(
                       (
                           SELECT jsonb_agg(value ORDER BY priority DESC, value)
                           FROM (
                               SELECT DISTINCT trim(token) AS value,
                                   CASE trim(token)
                                       WHEN '1mo' THEN 70 WHEN '1w' THEN 60 WHEN '1d' THEN 50
                                       WHEN '4h' THEN 40 WHEN '2h' THEN 35 WHEN '1h' THEN 30
                                       WHEN '30m' THEN 20 WHEN '15m' THEN 15 WHEN '5m' THEN 10
                                       WHEN '1m' THEN 5 ELSE 0
                                   END AS priority
                               FROM unnest(string_to_array(timeframe, ',')) AS token
                               WHERE trim(token) <> ''
                           ) contributors
                       ),
                       jsonb_build_array(split_part(timeframe, ',', 1))
                   )
        """))
        op.alter_column(table, "primary_timeframe", nullable=False)
        op.alter_column(table, "contributing_timeframes", nullable=False)
        op.create_index(f"ix_{table}_primary_timeframe", table, ["primary_timeframe"])
        # Retain the legacy column as a compatibility mirror of the primary timeframe.
        op.execute(sa.text(f"UPDATE {table} SET timeframe = primary_timeframe"))


def downgrade():
    for table in reversed(_TABLES):
        op.drop_index(f"ix_{table}_primary_timeframe", table_name=table)
        op.drop_column(table, "contributing_timeframes")
        op.drop_column(table, "primary_timeframe")
        op.alter_column(table, "timeframe", existing_type=sa.String(32), type_=sa.String(16), existing_nullable=False)
