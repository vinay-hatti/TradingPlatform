# revision identifiers, used by Alembic.
#revision: str = '1b0a35cdc5fb'
#down_revision: Union[str, Sequence[str], None] = 'e1ebcb5044fb'
#branch_labels: Union[str, Sequence[str], None] = None
#depends_on: Union[str, Sequence[str], None] = None

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from market.option_models import OptionContractHistory

#revision = "KEEP_GENERATED_REVISION"
#down_revision = "KEEP_GENERATED_DOWN_REVISION"
revision: str = '1b0a35cdc5fb'
down_revision: Union[str, Sequence[str], None] = 'e1ebcb5044fb'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "option_contract_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("underlying_symbol", sa.String(), nullable=False),
        sa.Column("option_symbol", sa.String(), nullable=False),
        sa.Column("quote_date", sa.Date(), nullable=False),
        sa.Column("expiry", sa.Date(), nullable=False),
        sa.Column("option_type", sa.String(), nullable=False),
        sa.Column("strike", sa.Float(), nullable=False),
        sa.Column("bid", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ask", sa.Float(), nullable=False, server_default="0"),
        sa.Column("mid", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last", sa.Float(), nullable=False, server_default="0"),
        sa.Column("volume", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("open_interest", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("implied_volatility", sa.Float(), nullable=False, server_default="0"),
        sa.Column("delta", sa.Float(), nullable=False, server_default="0"),
        sa.Column("gamma", sa.Float(), nullable=False, server_default="0"),
        sa.Column("theta", sa.Float(), nullable=False, server_default="0"),
        sa.Column("vega", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rho", sa.Float(), nullable=False, server_default="0"),
    )

    op.create_index(
        "ix_option_chain_lookup",
        "option_contract_history",
        ["underlying_symbol", "quote_date", "option_type", "expiry", "strike"],
    )

    op.create_index(
        "ix_option_chain_symbol",
        "option_contract_history",
        ["option_symbol"],
    )


def downgrade():
    op.drop_index("ix_option_chain_symbol", table_name="option_contract_history")
    op.drop_index("ix_option_chain_lookup", table_name="option_contract_history")
    op.drop_table("option_contract_history")
