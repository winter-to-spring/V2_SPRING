"""baseline schema for v2_spring ledger

Revision ID: 20260417_000001
Revises:
Create Date: 2026-04-17 20:00:00
"""
from __future__ import annotations

from alembic import op

from v2_spring.ledger.models import Base


revision = "20260417_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
