"""support: conversations, messages, claims, appeals, decisions, remedies

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

CLAIM_STATUSES = ("opened", "partner_discussion", "resolution_proposed", "partner_rejected",
                  "appealed", "internal_review", "decision_issued", "resolved", "withdrawn")
CLAIMS = ",".join(f"'{s}'" for s in CLAIM_STATUSES)


def _created_at():
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                     server_default=sa.func.now())


def _fk(name, target, ondelete=None, nullable=False):
    return sa.Column(name, sa.Uuid(), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(10), nullable=False),
        _fk("order_id", "orders.id", "CASCADE", nullable=True),
        _fk("request_id", "custom_requests.id", "CASCADE", nullable=True),
        sa.Column("claim_id", sa.Uuid(), nullable=True),
        _fk("partner_user_id", "users.id", "CASCADE", nullable=True),
        sa.Column("subject", sa.String(200), nullable=False),
        _fk("created_by", "users.id", "SET NULL", nullable=True),
        _created_at(),
        sa.UniqueConstraint("kind", "order_id", "request_id", "claim_id", "partner_user_id",
                            name="uq_conversations_context"),
        sa.CheckConstraint("kind in ('order','request','claim')", name="ck_conversations_kind_valid"),
    )
    op.create_table(
        "conversation_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("conversation_id", "conversations.id", "CASCADE"),
        _fk("user_id", "users.id", "CASCADE"),
        sa.Column("role_label", sa.String(20), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("conversation_id", "user_id", name="uq_conversation_members"),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("conversation_id", "conversations.id", "CASCADE"),
        _fk("sender_id", "users.id", "SET NULL", nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        _created_at(),
    )
    op.create_table(
        "claims",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("order_id", "orders.id", "CASCADE"),
        _fk("buyer_id", "users.id", "CASCADE"),
        sa.Column("target_role", sa.String(10), nullable=False),
        _fk("target_user_id", "users.id", "CASCADE"),
        sa.Column("component", sa.String(10), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="opened"),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        _created_at(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"status in ({CLAIMS})", name="ck_claims_status_valid"),
        sa.CheckConstraint("target_role in ('merchant','tailor')", name="ck_claims_target_valid"),
        sa.CheckConstraint("component in ('fabric','garment','shipping','service')",
                           name="ck_claims_component_valid"),
    )
    op.create_table(
        "claim_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("claim_id", "claims.id", "CASCADE"),
        _fk("uploaded_by", "users.id", "SET NULL", nullable=True),
        _fk("file_id", "files.id", "CASCADE"),
        sa.Column("note", sa.Text(), nullable=True),
        _created_at(),
    )
    op.create_table(
        "claim_responses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("claim_id", "claims.id", "CASCADE"),
        _fk("responder_id", "users.id", "SET NULL", nullable=True),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("proposal", postgresql.JSONB(), nullable=True),
        sa.Column("buyer_decision", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.CheckConstraint("kind in ('discussion','proposal','rejection')",
                           name="ck_claim_responses_kind_valid"),
        sa.CheckConstraint("buyer_decision in ('pending','accepted','rejected')",
                           name="ck_claim_responses_decision_valid"),
    )
    op.create_table(
        "appeals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("claim_id", "claims.id", "CASCADE"),
        _fk("rejection_id", "claim_responses.id", "CASCADE"),
        _fk("buyer_id", "users.id", "CASCADE"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
        _fk("reviewer_id", "users.id", "SET NULL", nullable=True),
        _created_at(),
        sa.UniqueConstraint("claim_id", name="uq_appeals_claim"),
        sa.CheckConstraint("status in ('pending','under_review','decided')",
                           name="ck_appeals_status_valid"),
    )
    op.create_table(
        "claim_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("appeal_id", "appeals.id", "CASCADE"),
        _fk("claim_id", "claims.id", "CASCADE"),
        _fk("reviewer_id", "users.id", "SET NULL", nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("remedy_type", sa.String(20), nullable=False),
        sa.Column("amount_idr", sa.BigInteger(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("requires_execution", sa.Boolean(), nullable=False, server_default="false"),
        _created_at(),
        sa.UniqueConstraint("appeal_id", name="uq_claim_decisions_appeal"),
        sa.CheckConstraint("outcome in ('upheld_rejection','overturned','partial')",
                           name="ck_claim_decisions_outcome_valid"),
        sa.CheckConstraint(
            "remedy_type in ('none','explanation','rework','replacement','refund_partial',"
            "'refund_full')", name="ck_claim_decisions_remedy_valid"),
    )
    op.create_table(
        "remedy_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("claim_id", "claims.id", "CASCADE"),
        _fk("actor_id", "users.id", "SET NULL", nullable=True),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("amount_idr", sa.BigInteger(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("simulated", sa.Boolean(), nullable=False, server_default="true"),
        _created_at(),
    )


def downgrade() -> None:
    for table in ("remedy_events", "claim_decisions", "appeals", "claim_responses",
                  "claim_evidence", "claims", "messages", "conversation_members",
                  "conversations"):
        op.drop_table(table)
