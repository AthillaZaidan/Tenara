"""ai: photo consents, body photos, cv analyses

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _created_at():
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                     server_default=sa.func.now())


def _fk(name, target, ondelete=None, nullable=False):
    return sa.Column(name, sa.Uuid(), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "photo_consents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("user_id", "users.id", "CASCADE"),
        sa.Column("purpose", sa.String(60), nullable=False),
        sa.Column("retention_minutes", sa.Integer(), nullable=False),
        sa.Column("share_original_with_tailor", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("allow_training_use", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notice_version", sa.String(20), nullable=False),
        _created_at(),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("retention_minutes > 0", name="ck_photo_consents_retention"),
    )
    op.create_table(
        "body_photos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("owner_id", "users.id", "CASCADE"),
        _fk("file_id", "files.id", "SET NULL", nullable=True),
        _fk("consent_id", "photo_consents.id"),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="stored"),
        sa.Column("delete_after", sa.DateTime(timezone=True), nullable=False),
        _created_at(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('stored','deleted')", name="ck_body_photos_status_valid"),
    )
    op.create_table(
        "cv_analyses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("owner_id", "users.id", "CASCADE"),
        _fk("listing_id", "fabric_listings.id", "SET NULL", nullable=True),
        _fk("file_id", "files.id", "SET NULL", nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("method", sa.String(120), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        _created_at(),
        sa.CheckConstraint("status in ('completed','failed')", name="ck_cv_analyses_status_valid"),
    )
    op.add_column("previews", _fk("body_photo_id", "body_photos.id", "SET NULL", nullable=True))


def downgrade() -> None:
    op.drop_column("previews", "body_photo_id")
    for table in ("cv_analyses", "body_photos", "photo_consents"):
        op.drop_table(table)
