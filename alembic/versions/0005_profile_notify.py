"""profile enrichment + notifications

Revision ID: 0005_profile_notify
Revises: 0004_profile_bindings
Create Date: 2026-09-20 17:30:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_profile_notify"
down_revision: Union[str, None] = "0004_profile_bindings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("phone", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("major", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("grade", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("degree", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("homepage_url", sa.String(length=512), nullable=True))
        batch.add_column(sa.Column("contact_email", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("city", sa.String(length=128), nullable=True))

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False, server_default="review"),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("is_read", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])


def downgrade() -> None:
    op.drop_index("ix_notifications_is_read", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("city")
        batch.drop_column("contact_email")
        batch.drop_column("homepage_url")
        batch.drop_column("degree")
        batch.drop_column("grade")
        batch.drop_column("major")
        batch.drop_column("phone")
