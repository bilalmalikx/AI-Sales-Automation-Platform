"""Keep opt-out suppression independently of contact deletion."""

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suppressed_emails",
        sa.Column("email", sa.String(255), primary_key=True),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.execute(
        sa.text(
            "INSERT INTO suppressed_emails (email, reason) SELECT lower(email), 'unsubscribed' FROM leads WHERE status = 'unsubscribed' AND email IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.drop_table("suppressed_emails")
