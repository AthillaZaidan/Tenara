"""AI avatar previews: the design (with its free style) drawn by an image model over a front picture of the
measurement-built body

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-19
"""
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_previews_kind_valid", "previews", type_="check")
    op.create_check_constraint("ck_previews_kind_valid", "previews",
                               "kind in ('product','on_body','avatar_3d','avatar_ai')")


def downgrade() -> None:
    op.execute("DELETE FROM previews WHERE kind = 'avatar_ai'")
    op.drop_constraint("ck_previews_kind_valid", "previews", type_="check")
    op.create_check_constraint("ck_previews_kind_valid", "previews", "kind in ('product','on_body','avatar_3d')")
