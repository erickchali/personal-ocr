"""enable pgvector and add transaction embedding

Revision ID: 4eac27c5dd34
Revises: 614fa53a3b0b
Create Date: 2026-04-21 00:57:36.151406

"""
from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4eac27c5dd34'
down_revision: Union[str, Sequence[str], None] = '614fa53a3b0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        'transactions',
        sa.Column('embedding', pgvector.sqlalchemy.Vector(1536), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('transactions', 'embedding')
