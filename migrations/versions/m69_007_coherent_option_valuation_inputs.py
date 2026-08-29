"""M69.7 coherent option valuation input provenance.

Revision ID: m69_007
Revises: m77_001
"""

from alembic import op
import sqlalchemy as sa


revision = "m69_007"
down_revision = "m77_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "option_contract_history",
        sa.Column("quote_timestamp", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "option_contract_history",
        sa.Column("source_underlying_price", sa.Float(), nullable=True),
    )
    op.create_index(
        "ix_option_contract_history_quote_timestamp",
        "option_contract_history",
        ["quote_timestamp"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_option_contract_history_quote_timestamp",
        table_name="option_contract_history",
    )
    op.drop_column("option_contract_history", "source_underlying_price")
    op.drop_column("option_contract_history", "quote_timestamp")
