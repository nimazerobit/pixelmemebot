from database.db import DatabaseManager
from models.status import BotStats, UserStats
from typing import Optional
import aiosqlite

class StatusRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    # --- Stats ---
    async def get_bot_stats(self) -> BotStats:
        async with aiosqlite.connect(self.db.path) as con:
            cur = await con.execute("""
            SELECT
                (SELECT COUNT(*) FROM users) AS total_users,
                (SELECT COUNT(*) FROM users WHERE banned = 1) AS banned_users,
                (SELECT COUNT(*) FROM users WHERE created_at >= strftime('%s','now','start of day')) AS today_users,
                (SELECT COUNT(*) FROM meme_usage) AS total_usage,
                (SELECT COUNT(*) FROM meme_usage WHERE created_at >= strftime('%s','now','start of day')) AS today_usage,
                (SELECT COUNT(*) FROM memes WHERE is_verified = 1 AND is_banned = 0) AS total_memes,
                (SELECT COUNT(*) FROM memes WHERE is_verified = 0 AND is_banned = 0) AS unverified_memes,
                (SELECT COUNT(*) FROM memes WHERE created_at >= strftime('%s','now','start of day')) AS today_memes
            """)
            row = await cur.fetchone()
            return BotStats(
                total_users=row[0], banned_users=row[1], today_users=row[2],
                total_usage=row[3], today_usage=row[4],
                total_memes=row[5], unverified_memes=row[6], today_memes=row[7]
            )

    async def get_user_stats(self, user_id: int) -> Optional[UserStats]:
        async with aiosqlite.connect(self.db.path) as con:
            cur = await con.execute("""
                SELECT
                    (SELECT COUNT(*) FROM memes WHERE publisher_user_id = ? AND is_verified = 1 AND is_banned = 0),
                    (SELECT COUNT(*) FROM memes WHERE publisher_user_id = ? AND is_verified = 0 AND is_banned = 0),
                    (SELECT COUNT(*) FROM memes WHERE publisher_user_id = ? AND created_at >= strftime('%s','now','start of day')),
                    (SELECT COUNT(*) FROM meme_usage WHERE user_id = ?),
                    (SELECT COUNT(*) FROM meme_usage WHERE user_id = ? AND created_at >= strftime('%s','now','start of day'))
                """, (user_id, user_id, user_id, user_id, user_id))
            row = await cur.fetchone()
            if not row or row[0] is None: return None
            return UserStats(
                total_memes=row[0], unverified_memes=row[1], today_memes=row[2],
                total_usage=row[3], today_usage=row[4]
            )
        
    async def get_top_publishers(self, limit: int = 10, timestamp: int = None) -> list[tuple[int, int, int]]:
        async with aiosqlite.connect(self.db.path) as con:
            where_clause = "m.is_verified = 1 AND m.is_banned = 0 AND u.banned = 0"
            if timestamp is not None:
                where_clause += f" AND m.created_at >= {timestamp}"
            cur = await con.execute(f"""
                SELECT
                    publisher_user_id,
                    full_name,
                    meme_count,
                    ROW_NUMBER() OVER (ORDER BY meme_count DESC) AS rank
                FROM (
                    SELECT
                        m.publisher_user_id,
                        u.full_name,
                        COUNT(*) AS meme_count
                    FROM memes m
                    JOIN users u ON u.user_id = m.publisher_user_id
                    WHERE {where_clause}
                    GROUP BY m.publisher_user_id, u.full_name
                )
                ORDER BY meme_count DESC
                LIMIT ?
            """, (limit,))

            rows = await cur.fetchall()
            return [(row[0], row[1], row[2], row[3]) for row in rows]
        
    async def get_publisher_rank(self, publisher_user_id: int, timestamp: int = None) -> tuple[int, int, int] | None:
        async with aiosqlite.connect(self.db.path) as con:
            where_clause = "m.is_verified = 1 AND m.is_banned = 0 AND u.banned = 0"
            if timestamp is not None:
                where_clause += f" AND m.created_at >= {timestamp}"
            cur = await con.execute(f"""
                WITH leaderboard AS (
                    SELECT
                        m.publisher_user_id,
                        COUNT(*) AS meme_count,
                        ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) AS rank
                    FROM memes m
                    JOIN users u ON u.user_id = m.publisher_user_id
                    WHERE
                        {where_clause}
                    GROUP BY m.publisher_user_id
                )
                SELECT publisher_user_id, meme_count, rank
                FROM leaderboard
                WHERE publisher_user_id = ?
            """, (publisher_user_id,))

            row = await cur.fetchone()
            return (row[0], row[1], row[2]) if row else None