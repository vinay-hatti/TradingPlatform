"""merge heads

Revision ID: 8f61c87039b5
Revises: d0f20a022b4a, e8a1a4451024
Create Date: 2026-06-27 13:12:59.202062

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f61c87039b5'
down_revision: Union[str, Sequence[str], None] = ('d0f20a022b4a', 'e8a1a4451024')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
