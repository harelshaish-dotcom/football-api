"""Add created_at to teams

Revision ID: ffb0fb0ef801
Revises: 9f55e7025f8d
Create Date: 2026-08-31 14:13:42.925943

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ffb0fb0ef801'
down_revision: Union[str, Sequence[str], None] = '9f55e7025f8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('teams', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('teams', 'created_at')
