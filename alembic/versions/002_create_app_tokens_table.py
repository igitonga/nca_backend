from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "app_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], 
            ["users.id"], 
            name="fk_app_tokens_user_id",
            ondelete="CASCADE"
        ),
    )
    op.create_index(op.f("ix_app_tokens_id"), "app_tokens", ["id"], unique=False)

    op.create_table(
        "metric_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("app_token_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=True),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("attributes", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"), 
        sa.ForeignKeyConstraint(
            ["app_token_id"], 
            ["app_tokens.id"], 
            name="fk_metric_events_app_token_id",
            ondelete="CASCADE"
        ),
    )
    op.create_index(op.f("ix_metric_events_id"), "metric_events", ["id"], unique=False)

def downgrade() -> None:
    op.drop_index(op.f("ix_metric_events_id"), table_name="metric_events")
    op.drop_table("metric_events")
    op.drop_index(op.f("ix_app_tokens_id"), table_name="app_tokens")
    op.drop_table("app_tokens")
