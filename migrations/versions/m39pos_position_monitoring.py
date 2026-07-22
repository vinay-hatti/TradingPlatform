"""Milestone 39 position monitoring and exit intelligence.
Revision ID: m39pos
Revises: m38exec
"""
from alembic import op
import sqlalchemy as sa
revision = "m39pos"
down_revision = "m38exec"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("position_monitoring_assessments",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("assessment_id",sa.String(64),nullable=False,unique=True),
        sa.Column("position_id",sa.String(128),nullable=False),sa.Column("portfolio_id",sa.String(128),nullable=False),
        sa.Column("symbol",sa.String(32),nullable=False),sa.Column("decision",sa.String(32),nullable=False),
        sa.Column("urgency",sa.String(32),nullable=False),sa.Column("return_pct",sa.Float(),nullable=False),
        sa.Column("payload",sa.JSON(),nullable=False),sa.Column("generated_at",sa.String(64),nullable=False))
    op.create_index("ix_m39_assessment_position","position_monitoring_assessments",["position_id"])
    op.create_index("ix_m39_assessment_portfolio","position_monitoring_assessments",["portfolio_id"])
    op.create_table("position_exit_instructions",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("instruction_id",sa.String(64),nullable=False,unique=True),
        sa.Column("assessment_id",sa.String(64),nullable=False),sa.Column("position_id",sa.String(128),nullable=False),
        sa.Column("action",sa.String(32),nullable=False),sa.Column("quantity",sa.Integer(),nullable=False),
        sa.Column("status",sa.String(32),nullable=False),sa.Column("payload",sa.JSON(),nullable=False),
        sa.Column("created_at",sa.String(64),nullable=False))
    op.create_index("ix_m39_instruction_position","position_exit_instructions",["position_id"])

def downgrade():
    op.drop_index("ix_m39_instruction_position",table_name="position_exit_instructions"); op.drop_table("position_exit_instructions")
    op.drop_index("ix_m39_assessment_portfolio",table_name="position_monitoring_assessments"); op.drop_index("ix_m39_assessment_position",table_name="position_monitoring_assessments"); op.drop_table("position_monitoring_assessments")
