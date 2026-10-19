"""Verified workspace members and revocable cookie sessions."""

import sqlalchemy as sa
from alembic import op

revision = "007_members_and_sessions"
down_revision = "006_discovery_schedules"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auth_users",
        sa.Column("email", sa.String(255), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(300), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("invited", sa.Boolean(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("verification_hash", sa.String(64), unique=True),
        sa.Column("verification_expires", sa.DateTime()),
        sa.Column("email_sent_at", sa.DateTime()),
        sa.Column("failed_logins", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime()),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "user_email",
            sa.String(255),
            sa.ForeignKey("auth_users.email", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_auth_sessions_user_email", "auth_sessions", ["user_email"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.execute(
        "UPDATE workspace_settings SET company='Skilledhat', sender='Skilledhat team' WHERE id=1"
    )
    op.execute(
        "UPDATE campaigns SET name=replace(name, 'Codelps', 'Skilledhat') WHERE name LIKE '%Codelps%'"
    )
    op.execute(
        "UPDATE discovery_schedules SET name=replace(name, 'Codelps', 'Skilledhat') WHERE name LIKE '%Codelps%'"
    )
    op.execute(
        "UPDATE email_drafts SET subject=replace(subject, 'Codelps', 'Skilledhat'), body=replace(body, 'Codelps', 'Skilledhat'), status='needs_review', approved_revision=NULL, revision=revision+1 WHERE status IN ('needs_review','approved','queued') AND (subject LIKE '%Codelps%' OR body LIKE '%Codelps%')"
    )


def downgrade():
    op.drop_table("auth_sessions")
    op.drop_table("auth_users")
