"""merge milestone 40 api heads

Revision ID: f1b98f37282f
Revises: 00898ab1e6b2, m40api
Create Date: 2026-07-22 00:07:36.624118

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1b98f37282f'
down_revision: Union[str, Sequence[str], None] = ('00898ab1e6b2', 'm40api')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
