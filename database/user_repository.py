from database.db import DatabaseManager
from models.user import User
from typing import Optional
import aiosqlite

class UserRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    # --- Users ---
    async def get(self, user_id: int) -> Optional[User]:
        async with aiosqlite.connect(self.db.path) as con:
            con.row_factory = aiosqlite.Row
            cur = await con.execute("SELECT user_id, banned, created_at FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            if row:
                return User(user_id=row['user_id'], banned=bool(row['banned']), created_at=row['created_at'])
            return None
        
    async def get_all_user_ids(self) -> list[int]:
        async with aiosqlite.connect(self.db.path) as con:
            cur = await con.execute("SELECT user_id FROM users")
            rows = await cur.fetchall()
            return [row['user_id'] for row in rows]

    async def upsert(self, user_id: int) -> None:
        async with aiosqlite.connect(self.db.path) as con:
            await con.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
            await con.commit()

    async def set_ban_status(self, user_id: int, is_banned: bool) -> None:
        async with aiosqlite.connect(self.db.path) as con:
            await con.execute("UPDATE users SET banned=? WHERE user_id=?", (1 if is_banned else 0, user_id))
            await con.commit()

    async def unban_all(self) -> int:
        async with aiosqlite.connect(self.db.path) as con:
            cur = await con.execute("SELECT COUNT(*) FROM users WHERE banned=1")
            count = (await cur.fetchone())[0]
            await con.execute("UPDATE users SET banned=0 WHERE banned=1")
            await con.commit()
            return count
