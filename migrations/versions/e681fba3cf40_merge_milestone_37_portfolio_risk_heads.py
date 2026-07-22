"""merge milestone 37 portfolio risk heads

Revision ID: e681fba3cf40
Revises: cfb47955f834, m37risk
Create Date: 2026-07-21 20:38:57.386005

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e681fba3cf40'
down_revision: Union[str, Sequence[str], None] = ('cfb47955f834', 'm37risk')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
