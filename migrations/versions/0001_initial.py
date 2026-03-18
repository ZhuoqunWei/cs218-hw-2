"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id         SERIAL PRIMARY KEY,
            name       TEXT NOT NULL,
            value      INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id    UUID PRIMARY KEY,
            customer_id TEXT NOT NULL,
            item_id     TEXT NOT NULL,
            quantity    INTEGER NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS ledger (
            ledger_id   UUID PRIMARY KEY,
            order_id    UUID NOT NULL REFERENCES orders(order_id),
            customer_id TEXT NOT NULL,
            amount      NUMERIC NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS idempotency_records (
            idempotency_key     TEXT PRIMARY KEY,
            request_fingerprint TEXT NOT NULL,
            response_body       TEXT NOT NULL,
            status_code         INTEGER NOT NULL,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ledger_order ON ledger(order_id)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS idempotency_records")
    op.execute("DROP TABLE IF EXISTS ledger")
    op.execute("DROP TABLE IF EXISTS orders")
    op.execute("DROP TABLE IF EXISTS items")
