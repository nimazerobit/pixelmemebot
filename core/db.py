import aiosqlite
import sqlite3
from pathlib import Path
from typing import List, Optional, Dict

class DB:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ---------- connections ----------
    def _connect_sync(self):
        con = sqlite3.connect(self.path, check_same_thread=False)
        con.row_factory = sqlite3.Row
        return con

    # ---------- init db ----------
    def _init_db(self):
        with self._connect_sync() as con:
            cur = con.cursor()
            
            # users
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                banned INTEGER DEFAULT 0
            );
            """)

            # memes
            cur.execute("""
            CREATE TABLE IF NOT EXISTS memes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                file_id TEXT NOT NULL,
                type TEXT NOT NULL,
                publisher_user_id INTEGER NOT NULL,
                is_verified INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                review_message_id INTEGER,
                review_chat_id INTEGER,
                created_at INTEGER DEFAULT (strftime('%s','now'))
            );
            """)

            # meme tags
            cur.execute("""
            CREATE TABLE IF NOT EXISTS meme_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meme_uuid TEXT NOT NULL,
                tag TEXT NOT NULL
            );
            """)

            # meme votes
            cur.execute("""
            CREATE TABLE IF NOT EXISTS meme_votes (
                meme_uuid TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                vote INTEGER NOT NULL,
                PRIMARY KEY (meme_uuid, user_id)
            );
            """)

            # meme usage
            cur.execute("""
            CREATE TABLE IF NOT EXISTS meme_usage (
                id INTEGER PRIMARY KEY,
                meme_uuid TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                query_text TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            );
            """)

            # indexes
            cur.execute("CREATE INDEX IF NOT EXISTS idx_memes_title ON memes(title COLLATE NOCASE);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_usage_user ON meme_usage(user_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tags_tag ON meme_tags(tag);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_memes_status ON memes(is_verified, is_banned);")
            con.commit()

    # ---------- user methods ----------
    async def get_user(self, user_id: int):
        async with aiosqlite.connect(self.path) as con:
            con.row_factory = aiosqlite.Row
            cur = await con.execute("SELECT banned, created_at FROM users WHERE user_id=?", (user_id,))
            return await cur.fetchone()

    async def upsert_user(self, user_id: int):
        async with aiosqlite.connect(self.path) as con:
            await con.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
            await con.commit()

    async def set_ban(self, user_id: int, value: bool):
        async with aiosqlite.connect(self.path) as con:
            await con.execute("UPDATE users SET banned=? WHERE user_id=?", (1 if value else 0, user_id))
            await con.commit()

    async def unban_all_users(self):
        async with aiosqlite.connect(self.path) as con:
            cur = await con.execute("SELECT COUNT(*) FROM users WHERE banned=1")
            count = (await cur.fetchone())[0]
            await con.execute("UPDATE users SET banned=0 WHERE banned=1")
            await con.commit()
            return count

    # ---------- meme management methods ----------
    async def add_meme(self, uuid, title, file_id, type_, publisher_user_id):
        async with aiosqlite.connect(self.path) as con:
            await con.execute("""
                INSERT INTO memes (uuid, title, file_id, type, publisher_user_id)
                VALUES (?, ?, ?, ?, ?)
            """, (uuid, title, file_id, type_, publisher_user_id))
            await con.commit()

    async def add_meme_tags(self, uuid: str, tags: list[str]):
        async with aiosqlite.connect(self.path) as con:
            await con.executemany(
                "INSERT INTO meme_tags (meme_uuid, tag) VALUES (?, ?)",
                [(uuid, t) for t in tags]
            )
            await con.commit()

    async def get_meme_info(self, uuid: str):
        async with aiosqlite.connect(self.path) as con:
            con.row_factory = aiosqlite.Row
            cur = await con.execute("SELECT * FROM memes WHERE uuid=?", (uuid,))
            meme = await cur.fetchone()
            if meme:
                cur = await con.execute("SELECT tag FROM meme_tags WHERE meme_uuid=?", (uuid,))
                tags = await cur.fetchall()
                return {**dict(meme), "tags": [row["tag"] for row in tags]}
            return None
        
    async def get_meme_tags(self, uuid: str) -> List[str]:
        async with aiosqlite.connect(self.path) as con:
            con.row_factory = sqlite3.Row
            cur = await con.execute("SELECT tag FROM meme_tags WHERE meme_uuid=?", (uuid,))
            rows = await cur.fetchall()
            return [row["tag"] for row in rows]

    def get_meme_publisher(self, uuid):
        with self._connect_sync() as con:
            cur = con.execute("SELECT publisher_user_id FROM memes WHERE uuid=?", (uuid,))
            row = cur.fetchone()
            return row[0] if row else None
        
    async def get_meme_by_file_id(self, file_id):
        async with aiosqlite.connect(self.path) as con:
            con.row_factory = aiosqlite.Row
            cur = await con.execute("SELECT * FROM memes WHERE file_id=?", (file_id,))
            return await cur.fetchone()
        
    async def get_meme_by_uuid(self, uuid):
        async with aiosqlite.connect(self.path) as con:
            con.row_factory = aiosqlite.Row
            cur = await con.execute("SELECT * FROM memes WHERE uuid=?", (uuid,))
            return await cur.fetchone()
    
    async def meme_file_exists(self, file_id: str) -> bool:
        async with aiosqlite.connect(self.path) as con:
            cur = await con.execute("SELECT 1 FROM memes WHERE file_id = ? LIMIT 1", (file_id,))
            return await cur.fetchone() is not None

    async def set_meme_verified(self, uuid: str, value: bool) -> None:
        async with aiosqlite.connect(self.path) as con:
            await con.execute("UPDATE memes SET is_verified=? WHERE uuid=?", (int(value), uuid))
            await con.commit()

    def set_meme_banned(self, uuid, value=True):
        with self._connect_sync() as con:
            con.execute("UPDATE memes SET is_banned=? WHERE uuid=?", (1 if value else 0, uuid))
            con.commit()

    async def delete_meme(self, uuid: str) -> bool:
        async with aiosqlite.connect(self.path) as con:
            try:
                await con.execute("BEGIN")
                cur = await con.execute("DELETE FROM memes WHERE uuid=?", (uuid,))
                if cur.rowcount == 0:
                    await con.rollback()
                    return False
                await con.execute("DELETE FROM meme_tags WHERE meme_uuid=?", (uuid,))
                await con.execute("DELETE FROM meme_votes WHERE meme_uuid=?", (uuid,))
                await con.execute("DELETE FROM meme_usage WHERE meme_uuid=?", (uuid,))
                await con.commit()
                return True
            except Exception:
                await con.rollback()
                raise

    # ---------- review system ----------
    def set_review_message(self, uuid, chat_id, message_id):
        with self._connect_sync() as con:
            con.execute("UPDATE memes SET review_chat_id=?, review_message_id=? WHERE uuid=?", (chat_id, message_id, uuid))
            con.commit()

    def get_review_message(self, uuid):
        with self._connect_sync() as con:
            con.row_factory = sqlite3.Row
            cur = con.execute("SELECT review_chat_id, review_message_id FROM memes WHERE uuid=?", (uuid,))
            return cur.fetchone()

    # ---------- voting system ----------
    async def upsert_vote(self, uuid, user_id, vote):
        async with aiosqlite.connect(self.path) as con:
            await con.execute("""
            INSERT INTO meme_votes (meme_uuid, user_id, vote) VALUES (?, ?, ?)
            ON CONFLICT(meme_uuid, user_id) DO UPDATE SET vote=excluded.vote
            """, (uuid, user_id, vote))
            await con.commit()

    async def get_vote_counts(self, uuid):
        async with aiosqlite.connect(self.path) as con:
            cur = await con.execute("""
            SELECT SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END), SUM(CASE WHEN vote=-1 THEN 1 ELSE 0 END)
            FROM meme_votes WHERE meme_uuid=?
            """, (uuid,))
            row = await cur.fetchone()
            return (row[0] or 0, row[1] or 0)

    async def get_user_vote(self, uuid: str, user_id: int) -> Optional[int]:
        async with aiosqlite.connect(self.path) as con:
            cur = await con.execute("SELECT vote FROM meme_votes WHERE meme_uuid=? AND user_id=?", (uuid, user_id))
            row = await cur.fetchone()
            return row[0] if row else None

    # ---------- inline system ----------

    async def get_inline_memes(self, user_id: int, query: str = "", limit: int = 50, offset: int = 0):
        async with aiosqlite.connect(self.path) as con:
            con.row_factory = aiosqlite.Row
            search_pattern = f"%{query}%" if query else ""
            sql = """
            SELECT m.uuid, m.file_id, m.title, m.type, m.created_at, MAX(mu.created_at) as last_used_ts
            FROM memes m
            LEFT JOIN meme_usage mu ON m.uuid = mu.meme_uuid AND mu.user_id = ?
            LEFT JOIN meme_tags mt ON m.uuid = mt.meme_uuid
            WHERE m.is_verified = 1 AND m.is_banned = 0
            AND (
                ? = ''  -- If query is empty, ignore search conditions
                OR m.title LIKE ? 
                OR mt.tag LIKE ?
            )
            GROUP BY m.uuid
            ORDER BY last_used_ts DESC NULLS LAST, m.created_at DESC
            LIMIT ? OFFSET ?
            """
            args = (user_id, query, search_pattern, search_pattern, limit, offset)
            cur = await con.execute(sql, args)
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

    async def get_meme_tags_map(self, uuids: list[str]) -> dict[str, str]:
        if not uuids:
            return {}
        placeholders = ",".join("?" for _ in uuids)
        async with aiosqlite.connect(self.path) as con:
            con.row_factory = aiosqlite.Row
            sql = f"SELECT meme_uuid, GROUP_CONCAT(tag, ', ') AS tags FROM meme_tags WHERE meme_uuid IN ({placeholders}) GROUP BY meme_uuid"
            cur = await con.execute(sql, tuple(uuids))
            rows = await cur.fetchall()
            return {row["meme_uuid"]: row["tags"] for row in rows}

    async def upsert_meme_usage(self, meme_uuid, user_id, query_text):
        async with aiosqlite.connect(self.path) as con:
            await con.execute("INSERT INTO meme_usage (meme_uuid, user_id, query_text) VALUES (?, ?, ?)", (meme_uuid, user_id, query_text))
            await con.commit()

    # ---------- bot status helper ----------
    async def bot_status(self):
        async with aiosqlite.connect(self.path) as con:
            cur = await con.execute(
            """
            SELECT
                -- users
                (SELECT COUNT(*) FROM users) AS total_users,
                (SELECT COUNT(*) FROM users WHERE banned = 1) AS banned_users,
                (SELECT COUNT(*) FROM users
                    WHERE created_at >= strftime('%s','now','start of day')
                ) AS today_users,

                -- meme usage
                (SELECT COUNT(*) FROM meme_usage) AS total_usage,
                (SELECT COUNT(*) FROM meme_usage
                    WHERE created_at >= strftime('%s','now','start of day')
                ) AS today_usage,

                -- memes
                (SELECT COUNT(*) FROM memes WHERE is_verified = 1 AND is_banned = 0) AS total_memes,
                (SELECT COUNT(*) FROM memes
                    WHERE is_verified = 0 AND is_banned = 0
                ) AS unverified_memes,
                (SELECT COUNT(*) FROM memes
                    WHERE created_at >= strftime('%s','now','start of day')
                ) AS today_memes
            """)
            row = await cur.fetchone()
            return row
        
    async def user_status(self, user_id: int):
        async with aiosqlite.connect(self.path) as con:
            cur = await con.execute(
                """SELECT
                    (SELECT COUNT(*) FROM memes WHERE publisher_user_id = ? AND is_verified = 1 AND is_banned = 0) AS total_memes,
                    (SELECT COUNT(*) FROM memes WHERE publisher_user_id = ? AND is_verified = 0 AND is_banned = 0) AS unverified_memes,
                    (SELECT COUNT(*) FROM memes WHERE publisher_user_id = ? AND created_at >= strftime('%s','now','start of day')) AS today_memes,
                    (SELECT COUNT(*) FROM meme_usage WHERE user_id = ?) AS total_usage,
                    (SELECT COUNT(*) FROM meme_usage WHERE user_id = ? AND created_at >= strftime('%s','now','start of day')) AS today_usage
                """, (user_id, user_id, user_id, user_id, user_id))
            row = await cur.fetchone()
            if row is None:
                return None
            return {
                "total_memes": row[0],
                "unverified_memes": row[1],
                "today_memes": row[2],
                "total_usage": row[3],
                "today_usage": row[4],
            }