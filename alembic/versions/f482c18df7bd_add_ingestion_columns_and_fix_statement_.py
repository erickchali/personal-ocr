"""add ingestion columns and fix statement_id index

Revision ID: f482c18df7bd
Revises: 614fa53a3b0b
Create Date: 2026-09-02 01:29:56.186654

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f482c18df7bd"
down_revision: Union[str, Sequence[str], None] = "614fa53a3b0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UQ_FILE_SHA256 = "uq_statement_file_sha256"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("statements", sa.Column("object_key", sa.String(), nullable=True))
    op.add_column("statements", sa.Column("file_sha256", sa.String(length=64), nullable=True))
    op.add_column("statements", sa.Column("status", sa.String(), server_default="pending", nullable=False))
    op.create_unique_constraint(UQ_FILE_SHA256, "statements", ["file_sha256"])

    # Rows that predate the upload pipeline were already reviewed through the old CLI
    # interrupt() gate, so the "pending" server_default would misrepresent them.
    op.execute("UPDATE statements SET status = 'approved' WHERE file_sha256 IS NULL")

    # This index was declared on statements(id), duplicating that table's primary key.
    # The column actually joined on is transactions.statement_id.
    op.drop_index("idx_transactions_statement_id", table_name="statements")
    op.create_index("idx_transactions_statement_id", "transactions", ["statement_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_transactions_statement_id", table_name="transactions")
    op.create_index("idx_transactions_statement_id", "statements", ["id"], unique=False)
    op.drop_constraint(UQ_FILE_SHA256, "statements", type_="unique")
    op.drop_column("statements", "status")
    op.drop_column("statements", "file_sha256")
    op.drop_column("statements", "object_key")
