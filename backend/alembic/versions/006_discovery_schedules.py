"""Daily discovery schedules and per-run provider budget reservations."""

import sqlalchemy as sa
from alembic import op

revision = "006_discovery_schedules"
down_revision = "005_mailbox_sync"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "discovery_runs",
        sa.Column("budget_reserved_usd", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_table(
        "discovery_schedules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column(
            "last_run_id", sa.Uuid(), sa.ForeignKey("discovery_runs.id", ondelete="SET NULL")
        ),
        sa.Column("last_checked_at", sa.DateTime()),
        sa.Column("error", sa.String(300)),
    )
    op.create_index("ix_discovery_schedules_due_at", "discovery_schedules", ["due_at"])


def downgrade():
    op.drop_table("discovery_schedules")
    op.drop_column("discovery_runs", "budget_reserved_usd")
