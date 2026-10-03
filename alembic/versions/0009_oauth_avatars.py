"""users.oauth_avatars for OAuth provider avatar URLs

Revision ID: 0009_oauth_avatars
Revises: 0008_liaison_messages
Create Date: 2026-10-03 10:10:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_oauth_avatars"
down_revision: Union[str, None] = "0008_liaison_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(users)")).fetchall()}
    if "oauth_avatars" not in cols:
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("oauth_avatars", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(users)")).fetchall()}
    if "oauth_avatars" in cols:
        with op.batch_alter_table("users") as batch:
            batch.drop_column("oauth_avatars")
