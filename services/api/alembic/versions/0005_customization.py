"""garment customization: templates, designs, measurements, estimates, previews

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _created_at():
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                     server_default=sa.func.now())


def _updated_at():
    return sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                     server_default=sa.func.now())


def _fk(name, target, ondelete=None, nullable=False):
    return sa.Column(name, sa.Uuid(), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)



def upgrade() -> None:
    op.create_table(
        "garment_templates",
        sa.Column("code", sa.String(3), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.CheckConstraint("code in ('T01','T02','T03','T04','T05')", name="ck_garment_templates_code"),
    )
    op.create_table(
        "template_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(3), sa.ForeignKey("garment_templates.code"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("definition_hash", sa.String(64), nullable=False),
        _created_at(),
        sa.UniqueConstraint("code", "version", name="uq_template_versions_code_version"),
    )
    op.create_table(
        "measurement_sets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("owner_id", "users.id", "CASCADE"),
        sa.Column("height_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint("status in ('draft','confirmed')", name="ck_measurement_sets_status_valid"),
    )
    op.create_table(
        "measurement_values",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("set_id", "measurement_sets.id", "CASCADE"),
        sa.Column("key", sa.String(40), nullable=False),
        sa.Column("value_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("original_value_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column("quality_flag", sa.String(30), nullable=True),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("history", postgresql.JSONB(), nullable=False, server_default="[]"),
        _updated_at(),
        sa.UniqueConstraint("set_id", "key", name="uq_measurement_values_set_key"),
        sa.CheckConstraint(
            "source in ('estimated','manual','corrected','manual_required','tailor')",
            name="ck_measurement_values_source_valid",
        ),
    )
    op.create_table(
        "customizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("buyer_id", "users.id", "CASCADE"),
        _fk("listing_id", "fabric_listings.id"),
        _fk("entry_id", "gallery_entries.id"),
        sa.Column("template_code", sa.String(3), nullable=False),
        _fk("template_version_id", "template_versions.id"),
        sa.Column("current_revision", sa.Integer(), nullable=False, server_default="1"),
        _fk("measurement_set_id", "measurement_sets.id", "SET NULL", nullable=True),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint("template_code in ('T01','T02','T03','T04','T05')",
                           name="ck_customizations_template_valid"),
    )
    op.create_table(
        "design_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("customization_id", "customizations.id", "CASCADE"),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=True),
        sa.Column("interpretation", postgresql.JSONB(), nullable=True),
        sa.Column("open_clarifications", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("reverted_from", sa.Integer(), nullable=True),
        _fk("created_by", "users.id", "SET NULL", nullable=True),
        _created_at(),
        sa.UniqueConstraint("customization_id", "revision", name="uq_design_revisions_rev"),
        sa.CheckConstraint("source in ('initial','prompt','manual','revert')",
                           name="ck_design_revisions_source_valid"),
    )
    op.create_table(
        "prompt_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("customization_id", "customizations.id", "CASCADE"),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("proposal", postgresql.JSONB(), nullable=False),
        sa.Column("interpreter", sa.String(40), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="proposed"),
        sa.Column("resulting_revision", sa.Integer(), nullable=True),
        _created_at(),
        sa.CheckConstraint("status in ('proposed','applied','discarded','superseded')",
                           name="ck_prompt_requests_status_valid"),
    )
    op.create_table(
        "material_estimates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("customization_id", "customizations.id", "CASCADE"),
        sa.Column("design_revision", sa.Integer(), nullable=False),
        _fk("measurement_set_id", "measurement_sets.id", "SET NULL", nullable=True),
        sa.Column("measurement_revision", sa.Integer(), nullable=True),
        sa.Column("listing_revision", sa.Integer(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="current"),
        _created_at(),
        sa.CheckConstraint("status in ('current','superseded')",
                           name="ck_material_estimates_status_valid"),
    )
    op.create_table(
        "previews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("customization_id", "customizations.id", "CASCADE"),
        sa.Column("design_revision", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("method", sa.String(80), nullable=True),
        _fk("file_id", "files.id", "SET NULL", nullable=True),
        sa.Column("warnings", postgresql.JSONB(), nullable=False, server_default="[]"),
        _fk("job_id", "jobs.id", "SET NULL", nullable=True),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint("kind in ('product','on_body')", name="ck_previews_kind_valid"),
    )


def downgrade() -> None:
    for table in ("previews", "material_estimates", "prompt_requests", "design_revisions",
                  "customizations", "measurement_values", "measurement_sets", "template_versions",
                  "garment_templates"):
        op.drop_table(table)
