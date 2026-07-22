"""empty message

Revision ID: cfb47955f834
Revises: 5a64f8ad63fb, m36c0mp
Create Date: 2026-07-21 20:04:25.534990

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cfb47955f834'
down_revision: Union[str, Sequence[str], None] = ('5a64f8ad63fb', 'm36c0mp')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
