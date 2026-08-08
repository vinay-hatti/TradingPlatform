"""M70 Polygon quote timestamp compatibility.
Revision ID: m70_002
Revises: m70_001
"""
from alembic import op
import sqlalchemy as sa
revision='m70_002';down_revision='m70_001';branch_labels=None;depends_on=None

def upgrade():
    op.alter_column('execution_intelligence_snapshots','quote_age_seconds',existing_type=sa.Float(),nullable=True)

def downgrade():
    op.execute("UPDATE execution_intelligence_snapshots SET quote_age_seconds=0 WHERE quote_age_seconds IS NULL")
    op.alter_column('execution_intelligence_snapshots','quote_age_seconds',existing_type=sa.Float(),nullable=False)
