"""add approved field to anime

Revision ID: 5d3f2a1c8e47
Revises: f9f3e6ee4c15
Create Date: 2026-01-22 14:47:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d3f2a1c8e47"
down_revision: Union[str, Sequence[str], None] = "f9f3e6ee4c15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("anime", sa.Column("approved", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("anime", "approved")
