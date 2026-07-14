from . import Migration
import sqlite3


class V6ScopeCanvasesByUser(Migration):
    version = 6
    description = "Add user_id to canvases for per-user project/session isolation"

    def up(self, conn: sqlite3.Connection) -> None:
        cursor = conn.execute("PRAGMA table_info(canvases)")
        columns = [column[1] for column in cursor.fetchall()]

        if "user_id" not in columns:
            conn.execute("ALTER TABLE canvases ADD COLUMN user_id TEXT")

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_canvases_user_updated
            ON canvases(user_id, updated_at DESC)
        """)

    def down(self, conn: sqlite3.Connection) -> None:
        # SQLite cannot easily drop a column; leave user_id in place on rollback.
        conn.execute("DROP INDEX IF EXISTS idx_canvases_user_updated")
