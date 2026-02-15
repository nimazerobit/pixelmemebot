from database.db import DatabaseManager
from models.meme import Meme
from models.status import BotStats, UserStats
from typing import Optional, List
import aiosqlite
import sqlite3

class MemeRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    # --- Memes ---
    async def create(self, meme: Meme) -> None:
        async with aiosqlite.connect(self.db.path) as con:
            await con.execute("""
                INSERT INTO memes (uuid, title, file_id, type, publisher_user_id)
                VALUES (?, ?, ?, ?, ?)
            """, (meme.uuid, meme.title, meme.file_id, meme.type, meme.publisher_user_id))
            await con.commit()

    async def get_by_uuid(self, uuid: str) -> Optional[Meme]:
        async with aiosqlite.connect(self.db.path) as con:
            con.row_factory = aiosqlite.Row
            cur = await con.execute("SELECT * FROM memes WHERE uuid=?", (uuid,))
            row = await cur.fetchone()
            if row:
                return self._row_to_meme(row)
            return None

    async def get_by_file_id(self, file_id: str) -> Optional[Meme]:
        async with aiosqlite.connect(self.db.path) as con:
            con.row_factory = aiosqlite.Row
            cur = await con.execute("SELECT * FROM memes WHERE file_id=?", (file_id,))
            row = await cur.fetchone()
            return self._row_to_meme(row) if row else None

    async def exists_by_file_id(self, file_id: str) -> bool:
        async with aiosqlite.connect(self.db.path) as con:
            cur = await con.execute("SELECT 1 FROM memes WHERE file_id = ? LIMIT 1", (file_id,))
            return await cur.fetchone() is not None
        
    async def update_title(self, uuid: str, new_title: str) -> None:
        async with aiosqlite.connect(self.db.path) as con:
            await con.execute("UPDATE memes SET title=? WHERE uuid=?", (new_title, uuid))
            await con.commit()

    async def update_tags(self, uuid: str, tags: List[str]) -> None:
        async with aiosqlite.connect(self.db.path) as con:
            await con.execute("DELETE FROM meme_tags WHERE meme_uuid=?", (uuid,))
            if tags:
                await con.executemany("INSERT INTO meme_tags (meme_uuid, tag) VALUES (?, ?)", [(uuid, t) for t in tags])
            await con.commit()

    async def update_verification(self, uuid: str, is_verified: bool) -> None:
        async with aiosqlite.connect(self.db.path) as con:
            await con.execute("UPDATE memes SET is_verified=? WHERE uuid=?", (1 if is_verified else 0, uuid))
            await con.commit()

    async def update_ban_status(self, uuid: str, is_banned: bool) -> None:
        async with aiosqlite.connect(self.db.path) as con:
            await con.execute("UPDATE memes SET is_banned=? WHERE uuid=?", (1 if is_banned else 0, uuid))
            await con.commit()

    async def get_all_unverified(self):
        async with aiosqlite.connect(self.db.path) as con:
            con.row_factory = aiosqlite.Row
            cur = await con.execute("SELECT * FROM memes WHERE is_verified=0 AND is_banned=0")
            rows = await cur.fetchall()
            return [self._row_to_meme(row) for row in rows]

    async def delete(self, uuid: str) -> bool:
        async with aiosqlite.connect(self.db.path) as con:
            try:
                await con.execute("BEGIN")
                cur = await con.execute("DELETE FROM memes WHERE uuid=?", (uuid,))
                if cur.rowcount == 0:
                    await con.rollback()
                    return False
                # Cascade deletes manually
                await con.execute("DELETE FROM meme_tags WHERE meme_uuid=?", (uuid,))
                await con.execute("DELETE FROM meme_votes WHERE meme_uuid=?", (uuid,))
                await con.execute("DELETE FROM meme_usage WHERE meme_uuid=?", (uuid,))
                await con.commit()
                return True
            except Exception:
                await con.rollback()
                raise

    # --- Review System ---
    def set_review_details(self, uuid: str, chat_id: int, message_id: int) -> None:
        with sqlite3.connect(self.db.path, check_same_thread=False) as con:
            con.execute("UPDATE memes SET review_chat_id=?, review_message_id=? WHERE uuid=?", (chat_id, message_id, uuid))
            con.commit()

    # --- Tags ---
    async def add_tags(self, uuid: str, tags: List[str]) -> None:
        async with aiosqlite.connect(self.db.path) as con:
            await con.executemany(
                "INSERT INTO meme_tags (meme_uuid, tag) VALUES (?, ?)",
                [(uuid, t) for t in tags]
            )
            await con.commit()

    async def get_tags(self, uuid: str) -> List[str]:
        async with aiosqlite.connect(self.db.path) as con:
            cur = await con.execute("SELECT tag FROM meme_tags WHERE meme_uuid=?", (uuid,))
            rows = await cur.fetchall()
            return [row[0] for row in rows]

    async def get_tags_map(self, uuids: List[str]) -> dict[str, str]:
        if not uuids: return {}
        placeholders = ",".join("?" for _ in uuids)
        async with aiosqlite.connect(self.db.path) as con:
            con.row_factory = aiosqlite.Row
            sql = f"SELECT meme_uuid, GROUP_CONCAT(tag, ', ') AS tags FROM meme_tags WHERE meme_uuid IN ({placeholders}) GROUP BY meme_uuid"
            cur = await con.execute(sql, tuple(uuids))
            rows = await cur.fetchall()
            return {row["meme_uuid"]: row["tags"] for row in rows}

    # --- Votes ---
    async def upsert_vote(self, uuid: str, user_id: int, vote: int) -> None:
        async with aiosqlite.connect(self.db.path) as con:
            await con.execute("""
            INSERT INTO meme_votes (meme_uuid, user_id, vote) VALUES (?, ?, ?)
            ON CONFLICT(meme_uuid, user_id) DO UPDATE SET vote=excluded.vote
            """, (uuid, user_id, vote))
            await con.commit()

    async def get_vote_stats(self, uuid: str) -> tuple[int, int]:
        async with aiosqlite.connect(self.db.path) as con:
            cur = await con.execute("""
            SELECT SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END), SUM(CASE WHEN vote=-1 THEN 1 ELSE 0 END)
            FROM meme_votes WHERE meme_uuid=?
            """, (uuid,))
            row = await cur.fetchone()
            return (row[0] or 0, row[1] or 0)

    async def get_user_vote(self, uuid: str, user_id: int) -> Optional[int]:
        async with aiosqlite.connect(self.db.path) as con:
            cur = await con.execute("SELECT vote FROM meme_votes WHERE meme_uuid=? AND user_id=?", (uuid, user_id))
            row = await cur.fetchone()
            return row[0] if row else None

    # --- Usage & Search ---
    async def log_usage(self, uuid: str, user_id: int, query_text: str) -> None:
        async with aiosqlite.connect(self.db.path) as con:
            await con.execute("INSERT INTO meme_usage (meme_uuid, user_id, query_text) VALUES (?, ?, ?)", (uuid, user_id, query_text))
            await con.commit()

    async def search_inline(self, user_id: int, query: str = "", limit: int = 50, offset: int = 0) -> List[dict]:
        async with aiosqlite.connect(self.db.path) as con:
            con.row_factory = aiosqlite.Row
            sql = """
            SELECT m.uuid, m.file_id, m.title, m.type, m.created_at, MAX(mu.created_at) as last_used_ts
            FROM memes m
            LEFT JOIN meme_usage mu ON m.uuid = mu.meme_uuid AND mu.user_id = ?
            """
            args = [user_id]
            where_conditions = ["m.is_verified = 1", "m.is_banned = 0"]
            keywords = query.strip().split() if query else []
            if keywords:
                for word in keywords:
                    search_pattern = f"%{word}%"
                    condition = """
                    (
                        m.title LIKE ? 
                        OR EXISTS (
                            SELECT 1 FROM meme_tags mt 
                            WHERE mt.meme_uuid = m.uuid AND mt.tag LIKE ?
                        )
                    )
                    """
                    where_conditions.append(condition)
                    args.extend([search_pattern, search_pattern])
            if where_conditions:
                sql += " WHERE " + " AND ".join(where_conditions)
            sql += """
            GROUP BY m.uuid
            ORDER BY last_used_ts DESC NULLS LAST, m.created_at DESC
            LIMIT ? OFFSET ?
            """
            args.extend([limit, offset])
            cur = await con.execute(sql, args)
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

    def _row_to_meme(self, row) -> Meme:
        return Meme(
            id=row['id'],
            uuid=row['uuid'],
            title=row['title'],
            file_id=row['file_id'],
            type=row['type'],
            publisher_user_id=row['publisher_user_id'],
            is_verified=bool(row['is_verified']),
            is_banned=bool(row['is_banned']),
            review_message_id=row['review_message_id'],
            review_chat_id=row['review_chat_id'],
            created_at=row['created_at']
        )
