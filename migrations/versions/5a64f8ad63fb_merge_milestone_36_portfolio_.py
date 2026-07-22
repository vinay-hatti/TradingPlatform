"""merge milestone 36 portfolio persistence heads

Revision ID: 5a64f8ad63fb
Revises: 1b0a35cdc5fb, f36a1s5
Create Date: 2026-07-21 18:30:29.254078

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a64f8ad63fb'
down_revision: Union[str, Sequence[str], None] = ('1b0a35cdc5fb', 'f36a1s5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
