"""remove user_id from app_tokens

Revision ID: 003
Revises: 002
Create Date: 2026-05-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("fk_app_tokens_user_id", "app_tokens", type_="foreignkey")
    op.drop_column("app_tokens", "user_id")


def downgrade() -> None:
    op.add_column(
        "app_tokens",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_app_tokens_user_id",
        "app_tokens",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
