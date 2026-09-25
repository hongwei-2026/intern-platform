"""enterprise ledger fields for review/audit/workflow

Revision ID: 0002_enterprise_ledger
Revises: 0001_initial
Create Date: 2026-03-22 12:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_enterprise_ledger"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GENESIS = "0" * 64


def upgrade() -> None:
    # --- review_records ---
    with op.batch_alter_table("review_records") as batch:
        batch.add_column(sa.Column("seq_no", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("actor_role", sa.Text(), nullable=True))
        batch.add_column(sa.Column("request_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("idempotency_key", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("decision_code", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("meta_json", sa.Text(), nullable=True))

    conn = op.get_bind()
    # backfill seq_no per application_id (by id order)
    rows = conn.execute(
        sa.text(
            "SELECT id, application_id FROM review_records ORDER BY application_id, id"
        )
    ).fetchall()
    counters: dict[int, int] = {}
    for row_id, application_id in rows:
        counters[application_id] = counters.get(application_id, 0) + 1
        conn.execute(
            sa.text(
                "UPDATE review_records SET seq_no = :seq, actor_role = :role "
                "WHERE id = :id"
            ),
            {"seq": counters[application_id], "role": "system", "id": row_id},
        )

    with op.batch_alter_table("review_records") as batch:
        batch.alter_column("seq_no", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("actor_role", existing_type=sa.Text(), nullable=False)
        batch.create_index("ix_review_records_request_id", ["request_id"])
        batch.create_unique_constraint(
            "uq_review_records_idempotency_key", ["idempotency_key"]
        )

    # --- audit_logs ---
    with op.batch_alter_table("audit_logs") as batch:
        batch.add_column(sa.Column("seq_no", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("event_hash", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("prev_hash", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("idempotency_key", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("actor_role", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column(
                "outcome",
                sa.String(length=16),
                nullable=False,
                server_default="SUCCESS",
            )
        )
        batch.add_column(sa.Column("trace_id", sa.String(length=64), nullable=True))

    audit_rows = conn.execute(
        sa.text("SELECT id FROM audit_logs ORDER BY id")
    ).fetchall()
    prev = GENESIS
    for idx, (row_id,) in enumerate(audit_rows, start=1):
        # placeholder chain for legacy rows; new writers use canonical hash
        placeholder = f"legacy-{idx}".ljust(64, "0")[:64]
        conn.execute(
            sa.text(
                "UPDATE audit_logs SET seq_no = :seq, prev_hash = :prev, "
                "event_hash = :eh WHERE id = :id"
            ),
            {"seq": idx, "prev": prev, "eh": placeholder, "id": row_id},
        )
        prev = placeholder

    with op.batch_alter_table("audit_logs") as batch:
        batch.alter_column("seq_no", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("event_hash", existing_type=sa.String(length=64), nullable=False)
        batch.alter_column("prev_hash", existing_type=sa.String(length=64), nullable=False)
        batch.create_index("ix_audit_logs_seq_no", ["seq_no"])
        batch.create_index("ix_audit_logs_trace_id", ["trace_id"])
        batch.create_unique_constraint(
            "uq_audit_logs_idempotency_key", ["idempotency_key"]
        )

    # --- workflow_events ---
    with op.batch_alter_table("workflow_events") as batch:
        batch.add_column(sa.Column("seq_no", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("event_hash", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("prev_hash", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("idempotency_key", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("actor_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("actor_role", sa.Text(), nullable=True))

    wf_rows = conn.execute(
        sa.text(
            "SELECT id, aggregate_type, aggregate_id FROM workflow_events "
            "ORDER BY aggregate_type, aggregate_id, id"
        )
    ).fetchall()
    wf_counters: dict[tuple[str, str], int] = {}
    wf_prev: dict[tuple[str, str], str] = {}
    for row_id, aggregate_type, aggregate_id in wf_rows:
        key = (aggregate_type, aggregate_id)
        wf_counters[key] = wf_counters.get(key, 0) + 1
        prev_h = wf_prev.get(key, GENESIS)
        placeholder = f"legacy-wf-{row_id}".ljust(64, "0")[:64]
        conn.execute(
            sa.text(
                "UPDATE workflow_events SET seq_no = :seq, prev_hash = :prev, "
                "event_hash = :eh WHERE id = :id"
            ),
            {"seq": wf_counters[key], "prev": prev_h, "eh": placeholder, "id": row_id},
        )
        wf_prev[key] = placeholder

    with op.batch_alter_table("workflow_events") as batch:
        batch.alter_column("seq_no", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("event_hash", existing_type=sa.String(length=64), nullable=False)
        batch.alter_column("prev_hash", existing_type=sa.String(length=64), nullable=False)
        batch.create_unique_constraint(
            "uq_workflow_events_idempotency_key", ["idempotency_key"]
        )


def downgrade() -> None:
    with op.batch_alter_table("workflow_events") as batch:
        batch.drop_constraint("uq_workflow_events_idempotency_key", type_="unique")
        batch.drop_column("actor_role")
        batch.drop_column("actor_id")
        batch.drop_column("idempotency_key")
        batch.drop_column("prev_hash")
        batch.drop_column("event_hash")
        batch.drop_column("seq_no")

    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_constraint("uq_audit_logs_idempotency_key", type_="unique")
        batch.drop_index("ix_audit_logs_trace_id")
        batch.drop_index("ix_audit_logs_seq_no")
        batch.drop_column("trace_id")
        batch.drop_column("outcome")
        batch.drop_column("actor_role")
        batch.drop_column("idempotency_key")
        batch.drop_column("prev_hash")
        batch.drop_column("event_hash")
        batch.drop_column("seq_no")

    with op.batch_alter_table("review_records") as batch:
        batch.drop_constraint("uq_review_records_idempotency_key", type_="unique")
        batch.drop_index("ix_review_records_request_id")
        batch.drop_column("meta_json")
        batch.drop_column("decision_code")
        batch.drop_column("idempotency_key")
        batch.drop_column("request_id")
        batch.drop_column("actor_role")
        batch.drop_column("seq_no")
