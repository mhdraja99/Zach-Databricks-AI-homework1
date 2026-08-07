import psycopg2
import os

from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine
from contextlib import contextmanager


def _lakebase_url() -> str:
    """Get the Lakebase connection URL from Databricks secrets.
    
    In production (Databricks Apps), reads from dbutils.secrets.
    For local development, falls back to LAKEBASE_URL environment variable.
    """
    try:
        # In Databricks Apps, use dbutils to access secrets
        from databricks.sdk.runtime import dbutils
        return dbutils.secrets.get(scope="database", key="lakebase-url")
    except (ImportError, Exception):
        # Fallback for local development - use environment variable
        url = os.getenv("LAKEBASE_URL")
        if not url:
            raise ValueError(
                "Lakebase URL not configured. "
                "Run setup_secrets.py to configure secrets, "
                "or set LAKEBASE_URL environment variable for local development."
            )
        return url

@contextmanager
def get_connection():
    """Yield a raw psycopg2 connection with a RealDictCursor factory."""
    conn = psycopg2.connect(_lakebase_url(), cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()

def get_engine():
    """Return a SQLAlchemy engine for Lakebase."""
    return create_engine(_lakebase_url())



def run_query(sql: str, params: tuple | dict | None = None) -> list[dict]:
    """Run a read query against Lakebase and return rows as list[dict]."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
        

def run_write(sql: str, params: tuple | dict | None = None) -> int:
    """Run an INSERT/UPDATE/DELETE against Lakebase, return affected row count."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount


def run_write_returning(sql: str, params: tuple | dict | None = None) -> list[dict]:
    """Run an INSERT/UPDATE/DELETE with RETURNING clause, commit and return rows."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.fetchall()