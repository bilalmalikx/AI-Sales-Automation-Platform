"""Durable IMAP checkpoints without deleting or marking customer mail as read."""

import sqlalchemy as sa
from alembic import op

revision = "005_mailbox_sync"
down_revision = "004_contactable"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mailbox_sync",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("uid_validity", sa.String(100), nullable=False),
        sa.Column("last_uid", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.String(300), nullable=True),
    )


def downgrade():
    op.drop_table("mailbox_sync")
