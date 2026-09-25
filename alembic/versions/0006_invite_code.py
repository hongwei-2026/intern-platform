"""communities.invite_code — 组织入驻通过后发放的组织码。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_invite_code"
down_revision = "0005_profile_notify"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {c["name"] for c in sa.inspect(conn).get_columns("communities")}
    if "invite_code" not in cols:
        with op.batch_alter_table("communities") as batch:
            batch.add_column(sa.Column("invite_code", sa.String(length=32), nullable=True))
    indexes = {ix["name"] for ix in sa.inspect(conn).get_indexes("communities")}
    if "ix_communities_invite_code" not in indexes:
        with op.batch_alter_table("communities") as batch:
            batch.create_index("ix_communities_invite_code", ["invite_code"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("communities") as batch:
        batch.drop_index("ix_communities_invite_code")
        batch.drop_column("invite_code")
