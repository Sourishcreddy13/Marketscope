"""Database-level append-only enforcement.

Adds SQLite triggers so trades, executed orders, order events, audit events and market ticks cannot be
altered or removed by raw SQL or any non-ORM caller (NFR-02). Earlier migrations are untouched (NFR-05).
"""
from alembic import op

revision = "0003_database_level_append_only"
down_revision = "0002_trade_ledger_and_idempotency"
branch_labels = None
depends_on = None

TRIGGERS = {
    "trg_trades_no_update": "CREATE TRIGGER trg_trades_no_update BEFORE UPDATE ON trades BEGIN SELECT RAISE(ABORT, 'trades are append-only'); END",
    "trg_trades_no_delete": "CREATE TRIGGER trg_trades_no_delete BEFORE DELETE ON trades BEGIN SELECT RAISE(ABORT, 'trades are append-only'); END",
    "trg_orders_executed_no_update": "CREATE TRIGGER trg_orders_executed_no_update BEFORE UPDATE ON orders WHEN OLD.status = 'EXECUTED' BEGIN SELECT RAISE(ABORT, 'executed orders are immutable'); END",
    "trg_orders_no_delete": "CREATE TRIGGER trg_orders_no_delete BEFORE DELETE ON orders BEGIN SELECT RAISE(ABORT, 'orders are never deleted'); END",
    "trg_order_events_no_update": "CREATE TRIGGER trg_order_events_no_update BEFORE UPDATE ON order_events BEGIN SELECT RAISE(ABORT, 'order events are append-only'); END",
    "trg_order_events_no_delete": "CREATE TRIGGER trg_order_events_no_delete BEFORE DELETE ON order_events BEGIN SELECT RAISE(ABORT, 'order events are append-only'); END",
    "trg_audit_events_no_update": "CREATE TRIGGER trg_audit_events_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END",
    "trg_audit_events_no_delete": "CREATE TRIGGER trg_audit_events_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END",
    "trg_market_ticks_no_update": "CREATE TRIGGER trg_market_ticks_no_update BEFORE UPDATE ON market_ticks BEGIN SELECT RAISE(ABORT, 'market ticks are append-only'); END",
    "trg_market_ticks_no_delete": "CREATE TRIGGER trg_market_ticks_no_delete BEFORE DELETE ON market_ticks BEGIN SELECT RAISE(ABORT, 'market ticks are append-only'); END",
}


def upgrade():
    for ddl in TRIGGERS.values():
        op.execute(ddl)


def downgrade():
    for name in TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
