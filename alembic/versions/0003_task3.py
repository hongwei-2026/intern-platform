"""task3: application messages + optimistic version

Revision ID: 0003_task3
Revises: 0002_enterprise_ledger
Create Date: 2026-03-22 18:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_task3"
down_revision: Union[str, None] = "0002_enterprise_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.add_column(
            sa.Column(
                "version",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )

    op.create_table(
        "application_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_application_messages_application_id",
        "application_messages",
        ["application_id"],
    )
    op.create_index(
        "ix_application_messages_sender_id",
        "application_messages",
        ["sender_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_application_messages_sender_id", table_name="application_messages")
    op.drop_index(
        "ix_application_messages_application_id", table_name="application_messages"
    )
    op.drop_table("application_messages")
    with op.batch_alter_table("applications") as batch:
        batch.drop_column("version")
