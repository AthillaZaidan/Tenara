"""appeals can be raised for partner no-response (explicit policy, not an implicit rejection)

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-08
"""
import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("appeals", "rejection_id", existing_type=sa.Uuid(), nullable=True)
    op.add_column("appeals", sa.Column("basis", sa.String(12), nullable=False,
                                       server_default="rejection"))
    op.create_check_constraint("ck_appeals_basis_valid", "appeals",
                               "basis in ('rejection','no_response')")


def downgrade() -> None:
    op.drop_constraint("ck_appeals_basis_valid", "appeals", type_="check")
    op.drop_column("appeals", "basis")
    op.alter_column("appeals", "rejection_id", existing_type=sa.Uuid(), nullable=False)
