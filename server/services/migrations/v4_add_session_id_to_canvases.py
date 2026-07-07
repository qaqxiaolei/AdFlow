from . import Migration
import sqlite3


class V4AddSessionIdToCanvases(Migration):
    version = 4
    description = "Add session_id to canvases table"

    def up(self, conn: sqlite3.Connection) -> None:
        cursor = conn.execute("PRAGMA table_info(canvases)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'session_id' not in columns:
            conn.execute("ALTER TABLE canvases ADD COLUMN session_id TEXT")

        cursor = conn.execute("""
            SELECT c.id, cs.id as session_id
            FROM canvases c
            LEFT JOIN chat_sessions cs ON c.id = cs.canvas_id
            WHERE c.session_id IS NULL AND cs.id IS NOT NULL
            GROUP BY c.id
        """)
        rows = cursor.fetchall()
        for row in rows:
            conn.execute("""
                UPDATE canvases SET session_id = ? WHERE id = ?
            """, (row[1], row[0]))

    def down(self, conn: sqlite3.Connection) -> None:
        cursor = conn.execute("PRAGMA table_info(canvases)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'session_id' in columns:
            conn.execute("""
                CREATE TABLE canvases_new (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    data TEXT,
                    description TEXT DEFAULT '',
                    thumbnail TEXT DEFAULT '',
                    created_at TEXT DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    updated_at TEXT DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
                )
            """)

            conn.execute("""
                INSERT INTO canvases_new (id, name, data, description, thumbnail, created_at, updated_at)
                SELECT id, name, data, description, thumbnail, created_at, updated_at FROM canvases
            """)

            conn.execute("DROP TABLE canvases")
            conn.execute("ALTER TABLE canvases_new RENAME TO canvases")