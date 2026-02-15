import sqlite3
from pathlib import Path

class DatabaseManager:
    def __init__(self, db_path: str):
        self.path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Synchronous initialization of tables."""
        con = sqlite3.connect(self.path, check_same_thread=False)
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
        con.close()
