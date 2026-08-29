"""M69.7.1 current valuation-run analytics lookup.

Revision ID: m69_008
Revises: m69_007
"""

from alembic import op


revision = "m69_008"
down_revision = "m69_007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_m69_snapshot_valuation_run_id
        ON institutional_option_valuation_snapshots
        ((payload_json ->> 'valuation_run_id'))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS ix_m69_snapshot_valuation_run_id
        """
    )
