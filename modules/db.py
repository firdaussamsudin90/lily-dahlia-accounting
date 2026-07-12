"""
Postgres (Supabase) connection helper for the app.

get_connection() returns a thin wrapper around a psycopg2 connection that
adds sqlite3-style .execute()/.executemany()/.executescript() convenience
methods returning the cursor directly (so `conn.execute(sql, params).fetchone()`
call sites written against the original SQLite prototype keep working
unchanged) — the actual SQL text still had to move to Postgres placeholder
style ('%s' instead of '?') and Postgres syntax, that part isn't papered over.

Row results come back as real dicts (via RealDictCursor), so `row["column"]`
access patterns from the SQLite version are unaffected.
"""
from pathlib import Path

import psycopg2
import psycopg2.extras

from modules.config import get_secret

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = BASE_DIR / "db" / "schema.sql"


class Connection:
    """sqlite3.Connection-shaped wrapper around a psycopg2 connection."""

    def __init__(self, pg_conn):
        self._conn = pg_conn

    def execute(self, query, params=None):
        cur = self._conn.cursor()
        cur.execute(query, params)
        return cur

    def executemany(self, query, seq_of_params):
        cur = self._conn.cursor()
        cur.executemany(query, seq_of_params)
        return cur

    def executescript(self, script):
        cur = self._conn.cursor()
        cur.execute(script)
        return cur

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_connection() -> Connection:
    dsn = get_secret("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to .streamlit/secrets.toml (local dev) or the "
            "app's Secrets settings (Streamlit Community Cloud) — see Getting_Started_Guide.md."
        )
    pg_conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    return Connection(pg_conn)


def init_db():
    # Local import: keeps db.seed_categorization_rules free of any import of
    # this module, avoiding a circular import between the two (Streamlit's
    # local-module reload watcher chases such cycles into runaway recursion).
    from db.seed_categorization_rules import seed_if_empty

    conn = get_connection()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    seed_if_empty(conn)
    conn.close()
