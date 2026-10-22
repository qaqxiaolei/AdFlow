from . import Migration
import sqlite3


class V8AddUserVideoCount(Migration):
    version = 8
    description = "Add users.video_count and backfill from successful video charges"

    def up(self, conn: sqlite3.Connection) -> None:
        cursor = conn.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        if "video_count" not in columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN video_count INTEGER NOT NULL DEFAULT 0"
            )

        # video:{model} is charged before generation; video_refund:{model} reverses a failure.
        # Net of the two is the historical successful generation count.
        conn.execute("""
            UPDATE users
            SET video_count = (
                SELECT MAX(
                    0,
                    COALESCE(SUM(
                        CASE
                            WHEN reason LIKE 'video:%' THEN 1
                            WHEN reason LIKE 'video_refund:%' THEN -1
                            ELSE 0
                        END
                    ), 0)
                )
                FROM credit_transactions
                WHERE credit_transactions.user_id = users.id
            )
        """)

    def down(self, conn: sqlite3.Connection) -> None:
        # SQLite cannot drop a column without rebuilding the table.
        pass
