"""add authentication audit actions

Revision ID: 20260519_0002
Revises: 20260519_0001
Create Date: 2026-05-19
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260519_0002"
down_revision: str | Sequence[str] | None = "20260519_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'login_success'")
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'login_failure'")
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'logout'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely without recreating dependent columns.
    pass
