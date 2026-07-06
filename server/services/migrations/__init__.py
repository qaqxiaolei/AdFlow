from typing import Protocol
import sqlite3

class Migration(Protocol):
    """迁移协议"""
    version: int
    description: str

    def up(self, conn: sqlite3.Connection) -> None:
        """应用迁移"""
        ...

    def down(self, conn: sqlite3.Connection) -> None:
        """回滚迁移"""
        ... 