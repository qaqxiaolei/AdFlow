import sqlite3
import json
import os
import re
from typing import List, Dict, Any, Optional
import aiosqlite
from .config_service import USER_DATA_DIR
from .migrations.manager import MigrationManager, CURRENT_VERSION

DB_PATH = os.path.join(USER_DATA_DIR, "localmanus.db")
MAX_CANVAS_COUNT = 3

class DatabaseService:
    def __init__(self):
        self.db_path = DB_PATH
        self._ensure_db_directory()
        self._migration_manager = MigrationManager()
        self._init_db()

    def _ensure_db_directory(self):
        """确保数据库目录存在"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def _init_db(self):
        """使用当前schema初始化数据库"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS db_version (
                    version INTEGER PRIMARY KEY
                )
            """)
            
            cursor = conn.execute("SELECT version FROM db_version")
            current_version = cursor.fetchone()
            print('local db version', current_version, 'latest version', CURRENT_VERSION)
            
            if current_version is None:
                conn.execute("INSERT INTO db_version (version) VALUES (0)")
                self._migration_manager.migrate(conn, 0, CURRENT_VERSION)
            elif current_version[0] < CURRENT_VERSION:
                print('Migrating database from version', current_version[0], 'to', CURRENT_VERSION)
                self._migration_manager.migrate(conn, current_version[0], CURRENT_VERSION)
    
    async def create_canvas(
        self, id: str, name: str, session_id: str = None, user_id: str = None
    ):
        """创建一个新的画布（归属指定用户）"""
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            await db.execute("""
                INSERT INTO canvases (id, name, session_id, user_id)
                VALUES (?, ?, ?, ?)
            """, (id, name, session_id, user_id))
            await db.commit()

    async def list_canvases(self, user_id: str) -> List[Dict[str, Any]]:
        """获取该用户最近的项目（最多保留 MAX_CANVAS_COUNT 个）"""
        await self.prune_canvases(user_id, MAX_CANVAS_COUNT)
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            db.row_factory = sqlite3.Row
            cursor = await db.execute("""
                SELECT id, name, description, thumbnail, created_at, updated_at, session_id
                FROM canvases
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (user_id, MAX_CANVAS_COUNT))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_canvas_owner(self, canvas_id: str) -> Optional[str]:
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            cursor = await db.execute(
                "SELECT user_id FROM canvases WHERE id = ?",
                (canvas_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return row[0]

    async def get_session_owner(self, session_id: str) -> Optional[str]:
        """通过会话关联的画布返回所属用户 id。"""
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            cursor = await db.execute(
                """
                SELECT c.user_id
                FROM chat_sessions s
                JOIN canvases c ON c.id = s.canvas_id
                WHERE s.id = ?
                """,
                (session_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return row[0]

    async def user_owns_canvas(self, canvas_id: str, user_id: str) -> bool:
        owner = await self.get_canvas_owner(canvas_id)
        return owner is not None and owner == user_id

    async def user_owns_session(self, session_id: str, user_id: str) -> bool:
        owner = await self.get_session_owner(session_id)
        return owner is not None and owner == user_id

    async def get_canvas_thumbnail(self, canvas_id: str) -> Optional[str]:
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            cursor = await db.execute(
                "SELECT thumbnail FROM canvases WHERE id = ?",
                (canvas_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return row[0] or None

    async def update_canvas_thumbnail(self, canvas_id: str, thumbnail: str):
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            await db.execute("""
                UPDATE canvases
                SET thumbnail = ?, updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
            """, (thumbnail, canvas_id))
            await db.commit()

    async def get_canvas_first_user_prompt(self, canvas_id: str) -> Optional[str]:
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                "SELECT session_id FROM canvases WHERE id = ?",
                (canvas_id,),
            )
            canvas_row = await cursor.fetchone()
            if not canvas_row:
                return None

            session_id = canvas_row["session_id"]
            if not session_id:
                cursor = await db.execute("""
                    SELECT id FROM chat_sessions
                    WHERE canvas_id = ?
                    ORDER BY updated_at DESC
                    LIMIT 1
                """, (canvas_id,))
                session_row = await cursor.fetchone()
                if not session_row:
                    return None
                session_id = session_row["id"]

            cursor = await db.execute("""
                SELECT message FROM chat_messages
                WHERE session_id = ? AND role = 'user'
                ORDER BY id ASC
                LIMIT 1
            """, (session_id,))
            message_row = await cursor.fetchone()
            if not message_row or not message_row["message"]:
                return None

            try:
                message = json.loads(message_row["message"])
            except json.JSONDecodeError:
                return None

            content = message.get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(str(item.get("text", "")))
                text = " ".join(parts)
            else:
                text = ""

            text = re.sub(
                r"<aspect_ratio>.*?</aspect_ratio>\s*",
                "",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            text = re.sub(
                r"<quantity>.*?</quantity>\s*",
                "",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            text = text.strip()
            return text or None

    async def prune_canvases(self, user_id: str, keep: int = MAX_CANVAS_COUNT):
        """只保留该用户最近的项目，删除更早的项目及其关联会话"""
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            cursor = await db.execute("""
                SELECT id FROM canvases
                WHERE user_id = ?
                ORDER BY updated_at DESC, created_at DESC
            """, (user_id,))
            rows = await cursor.fetchall()
            if len(rows) <= keep:
                return

            ids_to_delete = [row[0] for row in rows[keep:]]
            for canvas_id in ids_to_delete:
                await self._delete_canvas_related_data(db, canvas_id)
            await db.commit()

    async def _delete_canvas_related_data(self, db: aiosqlite.Connection, canvas_id: str):
        cursor = await db.execute(
            "SELECT id FROM chat_sessions WHERE canvas_id = ?",
            (canvas_id,),
        )
        session_rows = await cursor.fetchall()
        for session_row in session_rows:
            await db.execute(
                "DELETE FROM chat_messages WHERE session_id = ?",
                (session_row[0],),
            )
        await db.execute("DELETE FROM chat_sessions WHERE canvas_id = ?", (canvas_id,))
        await db.execute("DELETE FROM canvases WHERE id = ?", (canvas_id,))

    async def create_chat_session(self, id: str, model: str, provider: str, canvas_id: str, title: Optional[str] = None):
        """创建一个新的聊天会话"""
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            await db.execute("""
                INSERT OR REPLACE INTO chat_sessions (id, model, provider, canvas_id, title)
                VALUES (?, ?, ?, ?, ?)
            """, (id, model, provider, canvas_id, title))
            await db.commit()

    async def update_session_title(self, session_id: str, title: str):
        """更新聊天会话的标题，同时更新对应的 canvas name"""
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            
            await db.execute("""
                UPDATE chat_sessions SET title = ?, updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
            """, (title, session_id))
            
            await db.execute("""
                UPDATE canvases SET name = ?, updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE session_id = ?
            """, (title, session_id))
            
            await db.commit()

    async def create_message(self, session_id: str, role: str, message: str):
        """创建一个聊天消息"""
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            await db.execute("""
                INSERT INTO chat_messages (session_id, role, message)
                VALUES (?, ?, ?)
            """, (session_id, role, message))
            await db.commit()

    async def get_chat_history(self, session_id: str) -> List[Dict[str, Any]]:
        """获取聊天历史记录"""
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            db.row_factory = sqlite3.Row
            cursor = await db.execute("""
                SELECT role, message, id
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id ASC
            """, (session_id,))
            rows = await cursor.fetchall()
            
            messages = []
            for row in rows:
                row_dict = dict(row)
                if row_dict['message']:
                    try:
                        msg = json.loads(row_dict['message'])
                        messages.append(msg)
                    except:
                        pass
                
            return messages

    async def list_sessions(
        self, canvas_id: str, user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取聊天会话；指定 user_id 时按画布归属过滤。"""
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            db.row_factory = sqlite3.Row
            if canvas_id and user_id:
                cursor = await db.execute("""
                    SELECT s.id, s.title, s.model, s.provider, s.created_at, s.updated_at
                    FROM chat_sessions s
                    JOIN canvases c ON c.id = s.canvas_id
                    WHERE s.canvas_id = ? AND c.user_id = ?
                    ORDER BY s.updated_at DESC
                """, (canvas_id, user_id))
            elif canvas_id:
                cursor = await db.execute("""
                    SELECT id, title, model, provider, created_at, updated_at
                    FROM chat_sessions
                    WHERE canvas_id = ?
                    ORDER BY updated_at DESC
                """, (canvas_id,))
            elif user_id:
                cursor = await db.execute("""
                    SELECT s.id, s.title, s.model, s.provider, s.created_at, s.updated_at
                    FROM chat_sessions s
                    JOIN canvases c ON c.id = s.canvas_id
                    WHERE c.user_id = ?
                    ORDER BY s.updated_at DESC
                """, (user_id,))
            else:
                cursor = await db.execute("""
                    SELECT id, title, model, provider, created_at, updated_at
                    FROM chat_sessions
                    ORDER BY updated_at DESC
                """)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def save_canvas_data(
        self, id: str, data: str, thumbnail: str = None, user_id: str = None
    ) -> bool:
        """保存画布数据；指定 user_id 时校验归属。返回是否更新成功。"""
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            if user_id:
                cursor = await db.execute("""
                    UPDATE canvases
                    SET data = ?, thumbnail = ?, updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
                    WHERE id = ? AND user_id = ?
                """, (data, thumbnail, id, user_id))
            else:
                cursor = await db.execute("""
                    UPDATE canvases
                    SET data = ?, thumbnail = ?, updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
                    WHERE id = ?
                """, (data, thumbnail, id))
            await db.commit()
            return cursor.rowcount > 0

    async def get_canvas_data(
        self, id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """获取画布数据；指定 user_id 时仅返回该用户的画布。"""
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            db.row_factory = sqlite3.Row
            if user_id:
                cursor = await db.execute("""
                    SELECT data, name
                    FROM canvases
                    WHERE id = ? AND user_id = ?
                """, (id, user_id))
            else:
                cursor = await db.execute("""
                    SELECT data, name
                    FROM canvases
                    WHERE id = ?
                """, (id,))
            row = await cursor.fetchone()
            if not row:
                return None
            sessions = await self.list_sessions(id, user_id=user_id)
            return {
                'data': json.loads(row['data']) if row['data'] else {},
                'name': row['name'],
                'sessions': sessions
            }

    async def delete_canvas(self, id: str, user_id: str = None) -> bool:
        """删除画布及其关联会话；指定 user_id 时校验归属。"""
        if user_id and not await self.user_owns_canvas(id, user_id):
            return False
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            await self._delete_canvas_related_data(db, id)
            await db.commit()
            return True

    async def rename_canvas(self, id: str, name: str, user_id: str = None) -> bool:
        """重命名画布；指定 user_id 时校验归属。"""
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            if user_id:
                cursor = await db.execute(
                    "UPDATE canvases SET name = ? WHERE id = ? AND user_id = ?",
                    (name, id, user_id),
                )
            else:
                cursor = await db.execute(
                    "UPDATE canvases SET name = ? WHERE id = ?",
                    (name, id),
                )
            await db.commit()
            return cursor.rowcount > 0

    async def create_comfy_workflow(self, name: str, api_json: str, description: str, inputs: str, outputs: str = None):
        """创建一个新的Comfy 工作流"""
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            await db.execute("""
                INSERT INTO comfy_workflows (name, api_json, description, inputs, outputs)
                VALUES (?, ?, ?, ?, ?)
            """, (name, api_json, description, inputs, outputs))
            await db.commit()

    async def list_comfy_workflows(self) -> List[Dict[str, Any]]:
        """获取所有Comfy 工作流"""
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            db.row_factory = sqlite3.Row
            cursor = await db.execute("SELECT id, name, description, api_json, inputs, outputs FROM comfy_workflows ORDER BY id DESC")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def delete_comfy_workflow(self, id: int):
        """删除Comfy 工作流"""
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            await db.execute("DELETE FROM comfy_workflows WHERE id = ?", (id,))
            await db.commit()

    async def get_comfy_workflow(self, id: int):
        """获取Comfy 工作流字典表示"""
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                "SELECT api_json FROM comfy_workflows WHERE id = ?", (id,)
            )
            row = await cursor.fetchone()
        try:
            workflow_json = (
                row["api_json"]
                if isinstance(row["api_json"], dict)
                else json.loads(row["api_json"])
            )
            return workflow_json
        except json.JSONDecodeError as exc:
            raise ValueError(f"Stored workflow api_json is not valid JSON: {exc}")

    # ─── Users / auth / credits ───────────────────────────────────────────

    async def get_user_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE phone = ?", (phone,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def create_user(
        self, user_id: str, phone: str, password_hash: str, credits: float
    ) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            await db.execute(
                """
                INSERT INTO users (id, phone, password_hash, credits)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, phone, password_hash, credits),
            )
            if credits > 0:
                await db.execute(
                    """
                    INSERT INTO credit_transactions
                        (user_id, amount, balance_after, reason)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, credits, credits, "new_user_bonus"),
                )
            await db.commit()
        user = await self.get_user_by_id(user_id)
        assert user is not None
        return user

    async def save_sms_code(
        self, phone: str, code_hash: str, purpose: str, expires_at: str
    ) -> None:
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            # invalidate previous unused codes for same phone+purpose
            await db.execute(
                """
                UPDATE sms_codes SET used = 1
                WHERE phone = ? AND purpose = ? AND used = 0
                """,
                (phone, purpose),
            )
            await db.execute(
                """
                INSERT INTO sms_codes (phone, code_hash, purpose, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (phone, code_hash, purpose, expires_at),
            )
            await db.commit()

    async def verify_and_consume_sms_code(
        self, phone: str, code_hash: str, purpose: str
    ) -> bool:
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                """
                SELECT id FROM sms_codes
                WHERE phone = ? AND purpose = ? AND code_hash = ?
                  AND used = 0
                  AND expires_at > STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
                ORDER BY id DESC LIMIT 1
                """,
                (phone, purpose, code_hash),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            await db.execute(
                "UPDATE sms_codes SET used = 1 WHERE id = ?", (row["id"],)
            )
            await db.commit()
            return True

    async def get_user_credits(self, user_id: str) -> float:
        user = await self.get_user_by_id(user_id)
        if not user:
            return 0.0
        return float(user.get("credits") or 0)

    async def adjust_user_credits(
        self, user_id: str, amount: float, reason: str
    ) -> Dict[str, Any]:
        """增减积分。扣减不足时抛出 ValueError。"""
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                "SELECT credits FROM users WHERE id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                raise ValueError("用户不存在")
            current = float(row["credits"] or 0)
            new_balance = round(current + amount, 2)
            if new_balance < 0:
                raise ValueError("积分不足，请先充值")
            await db.execute(
                """
                UPDATE users
                SET credits = ?,
                    updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (new_balance, user_id),
            )
            await db.execute(
                """
                INSERT INTO credit_transactions
                    (user_id, amount, balance_after, reason)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, amount, new_balance, reason),
            )
            await db.commit()
            return {"credits": new_balance}

    # ─── Payment orders (WeChat recharge) ─────────────────────────────────

    async def create_payment_order(
        self,
        order_id: str,
        user_id: str,
        package_id: str,
        credits: float,
        amount_cents: int,
        code_url: str = "",
        channel: str = "wechat",
    ) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            await db.execute(
                """
                INSERT INTO payment_orders
                    (id, user_id, package_id, credits, amount_cents, status, channel, code_url)
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    order_id,
                    user_id,
                    package_id,
                    credits,
                    amount_cents,
                    channel,
                    code_url,
                ),
            )
            await db.commit()
        order = await self.get_payment_order(order_id)
        assert order is not None
        return order

    async def get_payment_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                "SELECT * FROM payment_orders WHERE id = ?", (order_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def mark_payment_order_paid(self, order_id: str, user_id: str) -> Dict[str, Any]:
        """
        幂等入账：仅 pending → paid 时加积分。
        返回 { already_paid, order, balance? }
        """
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                "SELECT * FROM payment_orders WHERE id = ?", (order_id,)
            )
            row = await cursor.fetchone()
            if not row:
                raise ValueError("订单不存在")
            order = dict(row)
            if order["user_id"] != user_id:
                raise ValueError("无权操作该订单")
            if order["status"] == "paid":
                return {"already_paid": True, "order": order}

            cursor = await db.execute(
                """
                UPDATE payment_orders
                SET status = 'paid',
                    paid_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'),
                    updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ? AND status = 'pending'
                """,
                (order_id,),
            )
            if cursor.rowcount == 0:
                refreshed = await self.get_payment_order(order_id)
                return {"already_paid": True, "order": refreshed or order}

            credits = float(order["credits"])
            cursor = await db.execute(
                "SELECT credits FROM users WHERE id = ?", (user_id,)
            )
            user_row = await cursor.fetchone()
            if not user_row:
                raise ValueError("用户不存在")
            new_balance = round(float(user_row["credits"] or 0) + credits, 2)
            await db.execute(
                """
                UPDATE users
                SET credits = ?,
                    updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (new_balance, user_id),
            )
            await db.execute(
                """
                INSERT INTO credit_transactions
                    (user_id, amount, balance_after, reason)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, credits, new_balance, f"recharge_wechat:{order['package_id']}"),
            )
            await db.commit()
            paid = await self.get_payment_order(order_id)
            return {
                "already_paid": False,
                "order": paid,
                "balance": new_balance,
            }

# Create a singleton instance
db_service = DatabaseService()
