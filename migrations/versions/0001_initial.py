"""Initial MarketScope schema.

All authoritative financial values are stored as INTEGER fixed-point units
with a scale of 10,000. The application exposes Python Decimal values.
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def fixed():
    return sa.BigInteger()


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_role_change_at", sa.DateTime(timezone=True)),
        sa.Column("last_role_change_by", sa.String(36)),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "stocks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sector", sa.String(128), nullable=False),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("symbol", name="uq_stocks_symbol"),
    )
    op.create_index("ix_stocks_symbol", "stocks", ["symbol"], unique=True)
    op.create_index("ix_stocks_sector", "stocks", ["sector"])
    op.create_index("ix_stocks_exchange", "stocks", ["exchange"])
    op.create_index("ix_stocks_status", "stocks", ["status"])

    op.create_table(
        "watchlists",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("customer_id", "name", name="uq_watchlist_customer_name"),
    )
    op.create_index("ix_watchlists_customer_id", "watchlists", ["customer_id"])

    op.create_table(
        "watchlist_symbols",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("watchlist_id", sa.String(36), sa.ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stock_id", sa.String(36), sa.ForeignKey("stocks.id"), nullable=False),
        sa.UniqueConstraint("watchlist_id", "stock_id", name="uq_watchlist_stock"),
    )
    op.create_index("ix_watchlist_symbols_watchlist_id", "watchlist_symbols", ["watchlist_id"])
    op.create_index("ix_watchlist_symbols_stock_id", "watchlist_symbols", ["stock_id"])

    op.create_table(
        "portfolios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("cash_balance", fixed(), nullable=False),
        sa.Column("reserved_cash", fixed(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("customer_id", name="uq_portfolios_customer_id"),
    )
    op.create_index("ix_portfolios_customer_id", "portfolios", ["customer_id"], unique=True)

    op.create_table(
        "portfolio_holdings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("portfolio_id", sa.String(36), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("stock_id", sa.String(36), sa.ForeignKey("stocks.id"), nullable=False),
        sa.Column("quantity", fixed(), nullable=False),
        sa.Column("average_buy_price", fixed(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("portfolio_id", "stock_id", name="uq_portfolio_stock"),
    )
    op.create_index("ix_portfolio_holdings_portfolio_id", "portfolio_holdings", ["portfolio_id"])
    op.create_index("ix_portfolio_holdings_stock_id", "portfolio_holdings", ["stock_id"])

    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("stock_id", sa.String(36), sa.ForeignKey("stocks.id"), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("order_type", sa.String(8), nullable=False),
        sa.Column("quantity", fixed(), nullable=False),
        sa.Column("limit_price", fixed(), nullable=True),
        sa.Column("quote_price", fixed(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("rejected_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text),
    )
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_index("ix_orders_stock_id", "orders", ["stock_id"])
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "order_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("from_status", sa.String(16)),
        sa.Column("to_status", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text),
    )
    op.create_index("ix_order_events_order_id", "order_events", ["order_id"])
    op.create_index("ix_order_events_actor_id", "order_events", ["actor_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_correlation_id", sa.String(64), nullable=False),
        sa.Column("details", sa.Text),
    )
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index("ix_audit_events_target_id", "audit_events", ["target_id"])

    op.create_table(
        "market_ticks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("stock_id", sa.String(36), sa.ForeignKey("stocks.id"), nullable=False),
        sa.Column("price", fixed(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_market_ticks_stock_id", "market_ticks", ["stock_id"])
    op.create_index("ix_market_ticks_occurred_at", "market_ticks", ["occurred_at"])


def downgrade():
    # Migration history is append-only. A downgrade is intentionally unsupported.
    raise RuntimeError("MarketScope migrations are append-only; do not downgrade merged history.")
