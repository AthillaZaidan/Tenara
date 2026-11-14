"""3D avatar previews: a preview kind built from a measurement set, which it remembers

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-14
"""
import sqlalchemy as sa

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_previews_kind_valid", "previews", type_="check")
    op.create_check_constraint("ck_previews_kind_valid", "previews", "kind in ('product','on_body','avatar_3d')")
    op.add_column("previews", sa.Column("measurement_set_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_previews_measurement_set_id_measurement_sets", "previews", "measurement_sets",
                          ["measurement_set_id"], ["id"], ondelete="SET NULL")
    op.add_column("previews", sa.Column("measurement_revision", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.execute("DELETE FROM previews WHERE kind = 'avatar_3d'")
    op.drop_column("previews", "measurement_revision")
    op.drop_constraint("fk_previews_measurement_set_id_measurement_sets", "previews", type_="foreignkey")
    op.drop_column("previews", "measurement_set_id")
    op.drop_constraint("ck_previews_kind_valid", "previews", type_="check")
    op.create_check_constraint("ck_previews_kind_valid", "previews", "kind in ('product','on_body')")
