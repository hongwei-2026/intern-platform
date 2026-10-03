"""社区对接消息表。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_liaison_messages"
down_revision = "0007_community_rich_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if sa.inspect(conn).has_table("liaison_messages"):
        return
    op.create_table(
        "liaison_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("community_id", sa.Integer(), sa.ForeignKey("communities.id"), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("peer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("liaison_messages")
