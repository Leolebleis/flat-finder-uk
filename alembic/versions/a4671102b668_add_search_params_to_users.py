"""add_search_params_to_users

Revision ID: a4671102b668
Revises: 01605aff669e
Create Date: 2026-06-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4671102b668"
down_revision: str | Sequence[str] | None = "01605aff669e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    if not _column_exists("users", "max_rent_pcm"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(sa.Column("max_rent_pcm", sa.Integer, nullable=True))
            batch_op.add_column(sa.Column("min_bedrooms", sa.Integer, nullable=True))
            batch_op.add_column(sa.Column("max_bedrooms", sa.Integer, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("max_bedrooms")
        batch_op.drop_column("min_bedrooms")
        batch_op.drop_column("max_rent_pcm")
