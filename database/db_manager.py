import sqlite3
import json
import logging
from typing import List, Dict, Optional, Tuple
from utils.config import Config
from utils.logging import get_logger

logger = get_logger("database")

class DBManager:
    def __init__(self, db_path: str = Config.DB_PATH):
        self.db_path = db_path
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initialize the database and create tables if they do not exist."""
        logger.info(f"Initializing SQLite database at: {self.db_path}")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Notifications Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                url TEXT UNIQUE,
                published_date TEXT,
                category TEXT,
                sha256_hash TEXT UNIQUE,
                notification_text TEXT,
                pdf_hash TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # 2. PDFs Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS pdfs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_url TEXT UNIQUE,
                pdf_hash TEXT,
                extracted_text TEXT,
                summary TEXT,
                important_dates TEXT, -- JSON string
                metadata TEXT,        -- JSON string
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # 3. Settings Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """)
            
            # 4. Logs Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT,
                module TEXT,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # Create indexes for fast querying
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_url ON notifications(url)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_hash ON notifications(sha256_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pdfs_url ON pdfs(pdf_url)")
            
            conn.commit()

    # --- Notifications Operations ---

    def add_notification(self, title: str, url: str, published_date: str, category: str, 
                         sha256_hash: str, notification_text: str, pdf_hash: str, status: str) -> bool:
        """Inserts a new notification into the database. Returns True if successful."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO notifications (title, url, published_date, category, sha256_hash, notification_text, pdf_hash, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (title, url, published_date, category, sha256_hash, notification_text, pdf_hash, status))
                conn.commit()
                return True
        except sqlite3.IntegrityError as e:
            logger.warning(f"Notification with hash or URL already exists. Details: {e}")
            return False
        except Exception as e:
            logger.error(f"Error adding notification to database: {e}")
            return False

    def update_notification(self, title: str, url: str, published_date: str, category: str, 
                            sha256_hash: str, notification_text: str, pdf_hash: str, status: str) -> bool:
        """Updates an existing notification based on URL."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                UPDATE notifications
                SET title = ?, published_date = ?, category = ?, sha256_hash = ?, 
                    notification_text = ?, pdf_hash = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE url = ?
                """, (title, published_date, category, sha256_hash, notification_text, pdf_hash, status, url))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating notification in database: {e}")
            return False

    def get_notification_by_url(self, url: str) -> Optional[dict]:
        """Fetches a single notification by URL."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notifications WHERE url = ?", (url,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_notification_by_hash(self, sha256_hash: str) -> Optional[dict]:
        """Fetches a single notification by SHA256 content hash."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notifications WHERE sha256_hash = ?", (sha256_hash,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_latest_notifications(self, limit: int = 5, category: str = None) -> List[dict]:
        """Fetches latest notifications sorted by creation date."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute("""
                SELECT * FROM notifications 
                WHERE category = ? AND status != 'SKIPPED'
                ORDER BY created_at DESC, id DESC LIMIT ?
                """, (category, limit))
            else:
                cursor.execute("""
                SELECT * FROM notifications 
                WHERE status != 'SKIPPED'
                ORDER BY created_at DESC, id DESC LIMIT ?
                """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def search_notifications(self, keyword: str, limit: int = 10) -> List[dict]:
        """Searches titles, notification texts, and summaries for a keyword."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # We perform a left join with pdfs to also search in extracted pdf texts
            query = """
            SELECT n.*, p.summary FROM notifications n
            LEFT JOIN pdfs p ON n.url = p.pdf_url
            WHERE (n.title LIKE ? OR n.notification_text LIKE ? OR p.extracted_text LIKE ? OR p.summary LIKE ?)
              AND n.status != 'SKIPPED'
            ORDER BY n.created_at DESC LIMIT ?
            """
            like_kw = f"%{keyword}%"
            cursor.execute(query, (like_kw, like_kw, like_kw, like_kw, limit))
            return [dict(row) for row in cursor.fetchall()]

    # --- PDF Operations ---

    def add_pdf(self, pdf_url: str, pdf_hash: str, extracted_text: str, summary: str, 
                important_dates: dict, metadata: dict) -> bool:
        """Inserts or replaces a parsed PDF entry."""
        try:
            dates_json = json.dumps(important_dates)
            meta_json = json.dumps(metadata)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO pdfs (pdf_url, pdf_hash, extracted_text, summary, important_dates, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (pdf_url, pdf_hash, extracted_text, summary, dates_json, meta_json))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding/replacing PDF record: {e}")
            return False

    def get_pdf_by_url(self, pdf_url: str) -> Optional[dict]:
        """Fetches PDF records by URL, decoding JSON fields."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pdfs WHERE pdf_url = ?", (pdf_url,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["important_dates"] = json.loads(res["important_dates"]) if res["important_dates"] else {}
            except Exception:
                res["important_dates"] = {}
            try:
                res["metadata"] = json.loads(res["metadata"]) if res["metadata"] else {}
            except Exception:
                res["metadata"] = {}
            return res

    # --- Settings Operations (Subscribers are stored here) ---

    def set_setting(self, key: str, value: str):
        """Stores a setting in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Gets a setting value from the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    def get_subscribers(self) -> Dict[str, str]:
        """Returns subscriber chat IDs and usernames as a dictionary."""
        val = self.get_setting("subscribed_chat_ids")
        if not val:
            return {}
        try:
            return json.loads(val)
        except Exception:
            return {}

    def subscribe_chat(self, chat_id: int, username: str = None) -> bool:
        """Adds a chat ID to the subscribers list. Returns True if newly subscribed."""
        subs = self.get_subscribers()
        cid = str(chat_id)
        if cid in subs:
            return False
        subs[cid] = username or ""
        self.set_setting("subscribed_chat_ids", json.dumps(subs))
        logger.info(f"Chat {chat_id} ({username}) subscribed successfully.")
        return True

    def unsubscribe_chat(self, chat_id: int) -> bool:
        """Removes a chat ID from the subscribers list. Returns True if removed."""
        subs = self.get_subscribers()
        cid = str(chat_id)
        if cid not in subs:
            return False
        del subs[cid]
        self.set_setting("subscribed_chat_ids", json.dumps(subs))
        logger.info(f"Chat {chat_id} unsubscribed successfully.")
        return True

    # --- Logs Table ---

    def add_db_log(self, level: str, module: str, message: str):
        """Stores application logs in database for easy retrieval."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO logs (level, module, message)
                VALUES (?, ?, ?)
                """, (level, module, message))
                conn.commit()
        except Exception as e:
            # Fallback to local logs directory if DB fails to log
            logger.error(f"Failed to write log to SQLite: {e}. Message: {message}")
