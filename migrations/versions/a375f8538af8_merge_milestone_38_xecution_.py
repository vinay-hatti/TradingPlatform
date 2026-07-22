"""merge milestone 38 xecution Orchestration heads

Revision ID: a375f8538af8
Revises: e681fba3cf40, m38exec
Create Date: 2026-07-21 21:16:45.981285

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a375f8538af8'
down_revision: Union[str, Sequence[str], None] = ('e681fba3cf40', 'm38exec')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
