"""product stories keep each sentence with its paragraph and sources (per-sentence source chips)

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-09
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_stories", sa.Column("sentences", postgresql.JSONB(), nullable=False,
                                               server_default="[]"))


def downgrade() -> None:
    op.drop_column("product_stories", "sentences")
