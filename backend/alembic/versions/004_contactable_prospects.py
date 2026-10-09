"""Index website-confirmed contact availability; preserve all discovery audit records."""

import sqlalchemy as sa
from alembic import op

revision = "004_contactable"
down_revision = "e762444138a9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "prospects",
        sa.Column("contact_available", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_prospects_contact_available", "prospects", ["contact_available"])
    table = sa.table(
        "prospects",
        sa.column("id", sa.Uuid()),
        sa.column("emails", sa.JSON()),
        sa.column("evidence", sa.JSON()),
        sa.column("contact_available", sa.Boolean()),
    )
    connection = op.get_bind()
    for row in connection.execute(
        sa.select(table.c.id, table.c.emails, table.c.evidence)
    ).mappings():
        site = (row["evidence"] or {}).get("website", {})
        available = bool(
            site.get("pages") and (row["emails"] or site.get("phones") or site.get("contact_links"))
        )
        if available:
            connection.execute(
                table.update().where(table.c.id == row["id"]).values(contact_available=True)
            )


def downgrade():
    op.drop_index("ix_prospects_contact_available", table_name="prospects")
    op.drop_column("prospects", "contact_available")
