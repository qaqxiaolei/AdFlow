from . import Migration
import sqlite3


class V7AddPaymentOrders(Migration):
    version = 7
    description = "Add payment_orders table for WeChat recharge"

    def up(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payment_orders (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                package_id TEXT NOT NULL,
                credits REAL NOT NULL,
                amount_cents INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                channel TEXT NOT NULL DEFAULT 'wechat',
                code_url TEXT,
                paid_at TEXT,
                created_at TEXT DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at TEXT DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_payment_orders_user
            ON payment_orders(user_id, created_at DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_payment_orders_status
            ON payment_orders(status)
        """)

    def down(self, conn: sqlite3.Connection) -> None:
        conn.execute("DROP TABLE IF EXISTS payment_orders")
