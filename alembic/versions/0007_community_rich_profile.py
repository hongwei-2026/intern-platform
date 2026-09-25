"""communities.tags + intro_body — 标签与富文本介绍帖。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_community_rich_profile"
down_revision = "0006_invite_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {c["name"] for c in sa.inspect(conn).get_columns("communities")}
    with op.batch_alter_table("communities") as batch:
        if "tags" not in cols:
            batch.add_column(sa.Column("tags", sa.Text(), nullable=True))
        if "intro_body" not in cols:
            batch.add_column(sa.Column("intro_body", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("communities") as batch:
        batch.drop_column("intro_body")
        batch.drop_column("tags")
