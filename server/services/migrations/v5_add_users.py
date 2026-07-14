from . import Migration
import sqlite3


class V5AddUsers(Migration):
    version = 5
    description = "Add users, sms_codes, and credit_transactions tables"

    def up(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                phone TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                credits REAL NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at TEXT DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sms_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                code_hash TEXT NOT NULL,
                purpose TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sms_codes_phone ON sms_codes(phone, purpose)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS credit_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                amount REAL NOT NULL,
                balance_after REAL NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

    def down(self, conn: sqlite3.Connection) -> None:
        conn.execute("DROP TABLE IF EXISTS credit_transactions")
        conn.execute("DROP TABLE IF EXISTS sms_codes")
        conn.execute("DROP TABLE IF EXISTS users")
