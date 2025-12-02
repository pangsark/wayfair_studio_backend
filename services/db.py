import os
from dotenv import load_dotenv
from typing import Optional
from .db_columns import StepColumn

parent_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(parent_env_path)

try:
    import psycopg2
    import psycopg2.extras
except Exception:
    psycopg2 = None

DATABASE_URL = os.getenv("DATABASE_URL")
def _get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set")
    if psycopg2 is None:
        raise RuntimeError("psycopg2 not installed")
    return psycopg2.connect(DATABASE_URL)


def _ensure_table_exists():
    try:
        conn = _get_connection()
    except RuntimeError:
        return

    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS manuals (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    description TEXT
                )
                """)

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS steps (
                    id SERIAL PRIMARY KEY,
                    manual_id INTEGER NOT NULL REFERENCES manuals(id) ON DELETE CASCADE,
                    step_number INTEGER NOT NULL,
                    description TEXT,
                    checklist TEXT,
                    image_url TEXT NOT NULL,
                    image_alt TEXT,
                    UNIQUE(manual_id, step_number)
                )
                """
            )


def get_cached_value(manual_id: int, step_number: int, column: StepColumn) -> Optional[dict]:
    """Fetch any column for a given manual and step"""
    try:
        conn = _get_connection()
    except RuntimeError:
        return None

    # ensure table exists so first-run is friendly
    _ensure_table_exists()

    column_name = column.value

    with conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            query = f"""
                SELECT {column_name}
                FROM steps WHERE manual_id = %s AND step_number = %s
                """ 
            cur.execute(query, (manual_id, step_number))
            row = cur.fetchone()
            if row:
                return {"manual_id": manual_id, "step": step_number, column_name: row[column_name]}

    return None


def store_value(manual_id: int, step_number: int, column: StepColumn, value: str) -> None:
    """Insert or update a value into the DB. Safely no-ops if DB not configured."""
    try:
        conn = _get_connection()
    except RuntimeError:
        return

    _ensure_table_exists()

    column_name = column.value

    with conn:
        with conn.cursor() as cur:
            query = f"""
                UPDATE steps
                SET {column_name} = %s
                WHERE manual_id = %s AND step_number = %s
                """
            cur.execute(query, (value, manual_id, step_number))
