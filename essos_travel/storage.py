import json
import sqlite3
from pathlib import Path

from .config import private_dir


class Store:
    def __init__(self, path):
        path = Path(path)
        private_dir(path.parent)
        self.db = sqlite3.connect(path)
        path.chmod(0o600)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
              id TEXT PRIMARY KEY, session TEXT NOT NULL, status TEXT NOT NULL,
              response TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS cursors (id TEXT PRIMARY KEY, value INTEGER NOT NULL);
        """)

    def load(self, session):
        row = self.db.execute("SELECT value FROM sessions WHERE id=?", (session,)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, session, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO sessions VALUES (?,?)", (session, json.dumps(value)))

    def claim(self, event, session):
        with self.db:
            result = self.db.execute("INSERT OR IGNORE INTO events(id,session,status) VALUES (?,?, 'processing')", (event, session))
        return result.rowcount == 1

    def mark(self, event, status, response=None):
        with self.db:
            self.db.execute("UPDATE events SET status=?, response=COALESCE(?,response) WHERE id=?", (status, response, event))

    def cursor(self, name):
        row = self.db.execute("SELECT value FROM cursors WHERE id=?", (name,)).fetchone()
        return row[0] if row else None

    def set_cursor(self, name, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO cursors VALUES (?,?)", (name, value))
