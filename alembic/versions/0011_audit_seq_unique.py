"""unique audit_logs.seq_no for hash-chain integrity

Revision ID: 0011_audit_seq_unique
Revises: 0010_email_codes
Create Date: 2026-10-04 12:40:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0011_audit_seq_unique"
down_revision: Union[str, None] = "0010_email_codes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint("uq_audit_logs_seq_no", "audit_logs", ["seq_no"])


def downgrade() -> None:
    op.drop_constraint("uq_audit_logs_seq_no", "audit_logs", type_="unique")
