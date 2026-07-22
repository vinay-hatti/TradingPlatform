"""merge milestone 39 Position Monitoring heads

Revision ID: 00898ab1e6b2
Revises: a375f8538af8, m39pos
Create Date: 2026-07-21 21:38:42.622729

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00898ab1e6b2'
down_revision: Union[str, Sequence[str], None] = ('a375f8538af8', 'm39pos')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
