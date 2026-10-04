"""Append-only trade ledger and order idempotency.

Adds the typed, append-only `trades` execution ledger and the idempotency columns on `orders`.
Migration 0001 is intentionally untouched (NFR-05: merged migrations are append-only).
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_trade_ledger_and_idempotency"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orders", sa.Column("idempotency_key", sa.String(64), nullable=True))
    op.add_column("orders", sa.Column("request_fingerprint", sa.String(64), nullable=True))
    op.create_index("uq_orders_customer_idempotency", "orders", ["customer_id", "idempotency_key"], unique=True)

    op.create_table(
        "trades",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("stock_id", sa.String(36), sa.ForeignKey("stocks.id"), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("execution_price", sa.BigInteger(), nullable=False),
        sa.Column("notional", sa.BigInteger(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("request_correlation_id", sa.String(64), nullable=False),
    )
    op.create_index("ix_trades_order_id", "trades", ["order_id"], unique=True)
    op.create_index("ix_trades_customer_id", "trades", ["customer_id"])
    op.create_index("ix_trades_stock_id", "trades", ["stock_id"])
    op.create_index("ix_trades_executed_at", "trades", ["executed_at"])
    op.create_index("ix_trades_actor_id", "trades", ["actor_id"])


def downgrade():
    raise RuntimeError("MarketScope migrations are append-only; do not downgrade merged history.")
