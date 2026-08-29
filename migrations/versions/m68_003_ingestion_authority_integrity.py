"""M68.2.1.9 exact-current ingestion authority integrity.

The schema contract remains the single M68.2.1.8 authority migration.

Revision ID: m68_003
Revises: m68_002
"""

from alembic import op
import sqlalchemy as sa


revision = "m68_003"
down_revision = "m68_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "institutional_inflection_snapshots",
        "coverage_status",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "institutional_inflection_publications",
        "coverage_status",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute("""
        UPDATE institutional_inflection_snapshots
           SET coverage_status = LEFT(coverage_status, 32)
         WHERE LENGTH(coverage_status) > 32
    """)
    op.execute("""
        UPDATE institutional_inflection_publications
           SET coverage_status = LEFT(coverage_status, 32)
         WHERE LENGTH(coverage_status) > 32
    """)
    op.alter_column(
        "institutional_inflection_publications",
        "coverage_status",
        existing_type=sa.String(length=64),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
    op.alter_column(
        "institutional_inflection_snapshots",
        "coverage_status",
        existing_type=sa.String(length=64),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
