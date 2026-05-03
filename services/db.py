"""
Database access layer for Wayfair Studio.

All public functions follow a "safe no-op" pattern: if DATABASE_URL is not
set or psycopg2 is unavailable, they return sensible defaults (None, [], or
silently skip writes) rather than raising. This lets the application run in a
database-less environment for local development with filesystem-only manuals.

Tables managed here:
  manuals  — manual metadata
  steps    — per-step data with AI-generated caches (description, orientation_text)
  pages    — per-page data used during PDF ingestion (suggested/confirmed boxes)
"""
import os
from dotenv import load_dotenv
from typing import List, Optional
from .db_columns import StepColumn

parent_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(parent_env_path)

try:
    import psycopg2
    import psycopg2.extras
except Exception:
    psycopg2 = None

DATABASE_URL = os.getenv("DATABASE_URL")

# NOTE: _dbg_log and its call sites below are leftover development instrumentation.
# They write to a hardcoded local path and have no effect in other environments
# (all calls are wrapped in try/except). Remove before production deployment.
import json as _dbg_json
def _dbg_log(hyp, msg, data):
    try:
        import time
        with open("/Users/aaronzhang/Desktop/wayfair_studio_backend/.cursor/debug.log", "a") as f:
            safe_data = {k: (v[:20] + "..." if isinstance(v, str) and len(v) > 30 else v) for k, v in data.items()}
            f.write(_dbg_json.dumps({"hypothesisId": hyp, "location": "db.py", "message": msg, "data": safe_data, "timestamp": int(time.time() * 1000)}) + "\n")
    except: pass

def _get_connection():
    # region agent log
    _dbg_log("A,B,E", "DATABASE_URL value check", {"url_set": DATABASE_URL is not None, "url_prefix": DATABASE_URL[:40] if DATABASE_URL else "None", "env_file_path": parent_env_path, "env_file_exists": os.path.exists(parent_env_path)})
    # Parse URL to check password details (not the actual password)
    if DATABASE_URL and "://" in DATABASE_URL:
        try:
            creds_part = DATABASE_URL.split("://")[1].split("@")[0]  # user:pass
            if ":" in creds_part:
                user, pwd = creds_part.split(":", 1)
                _dbg_log("B", "URL credentials check", {"user": user, "pwd_len": len(pwd), "pwd_starts": pwd[:2] if pwd else "", "pwd_ends": pwd[-2:] if len(pwd) >= 2 else ""})
            else:
                _dbg_log("B", "URL has no password separator", {"creds_part": creds_part})
        except: pass
    # #endregion
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set")
    if psycopg2 is None:
        raise RuntimeError("psycopg2 not installed")
    # #region agent log
    _dbg_log("C,D", "Attempting psycopg2.connect", {"url_host_part": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "no_at_sign"})
    # #endregion
    try:
        conn = psycopg2.connect(DATABASE_URL)
        # #region agent log
        _dbg_log("ALL", "Connection successful", {"status": "ok"})
        # #endregion
        return conn
    except Exception as e:
        # #region agent log
        _dbg_log("ALL", "Connection failed", {"error_type": type(e).__name__, "error_msg": str(e)[:100]})
        # #endregion
        raise


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
                    description TEXT,
                    product_image_url TEXT,
                    status TEXT
                )
                """)

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS steps (
                    id SERIAL PRIMARY KEY,
                    manual_id INTEGER NOT NULL REFERENCES manuals(id) ON DELETE CASCADE,
                    step_number INTEGER NOT NULL,
                    description TEXT,
                    tools TEXT[],
                    image_url TEXT NOT NULL,
                    orientation_text JSONB,
                    UNIQUE(manual_id, step_number)
                )
                """
            )
            cur.execute(
               """
               CREATE TABLE IF NOT EXISTS pages (
                   id SERIAL PRIMARY KEY,
                   manual_id INTEGER NOT NULL REFERENCES manuals(id) ON DELETE CASCADE,
                   page_number INTEGER NOT NULL,
                   image_url TEXT NOT NULL,
                   suggested_boxes JSONB,
                   final_boxes JSONB,
                   status TEXT,
                   UNIQUE(manual_id, page_number)
                )
                """
            )
            cur.execute("ALTER TABLE steps ADD COLUMN IF NOT EXISTS orientation_text JSONB")


def get_cached_value(manual_id: int, step_number: int, column: StepColumn, returnMetadata: bool = True) -> Optional[dict]:
    """Fetch any column for a given manual and step"""
    try:
        conn = _get_connection()
    except RuntimeError:
        return None

    column_name = column.value

    with conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            query = f"""
                SELECT {column_name}
                FROM steps WHERE manual_id = %s AND step_number = %s
                """ 
            cur.execute(query, (manual_id, step_number))
            row = cur.fetchone()
            if row and returnMetadata:
                return {"manual_id": manual_id, "step": step_number, column_name: row[column_name]}
            elif row:
                return row[column_name]

    return None


def store_value(manual_id: int, step_number: int, column: StepColumn, value: str) -> None:
    """Insert or update a value into the DB. Safely no-ops if DB not configured."""
    try:
        conn = _get_connection()
    except RuntimeError:
        return

    column_name = column.value

    with conn:
        with conn.cursor() as cur:
            query = f"""
                UPDATE steps
                SET {column_name} = %s
                WHERE manual_id = %s AND step_number = %s
                """
            cur.execute(query, (value, manual_id, step_number))


def ensure_manual_and_step(
    manual_id: int,
    step_number: int,
    image_url: str,
    manual_name: Optional[str] = None,
    manual_slug: Optional[str] = None,
) -> None:
    """
    Ensure a row exists in manuals for manual_id and a row in steps for
    (manual_id, step_number). Inserts with defaults if missing. No-op if DB not configured.
    """
    try:
        conn = _get_connection()
    except RuntimeError:
        return

    with conn:
        with conn.cursor() as cur:
            name = manual_name or f"Manual {manual_id}"
            slug = manual_slug or f"manual-{manual_id}"
            cur.execute(
                """
                INSERT INTO manuals (id, name, slug, description, product_image_url)
                VALUES (%s, %s, %s, NULL, NULL)
                ON CONFLICT (id) DO NOTHING
                """,
                (manual_id, name, slug),
            )
            cur.execute(
                """
                INSERT INTO steps (manual_id, step_number, image_url)
                VALUES (%s, %s, %s)
                ON CONFLICT (manual_id, step_number) DO NOTHING
                """,
                (manual_id, step_number, image_url),
            )


def get_product_image_url(manual_id: int) -> Optional[str]:
    """Get the colored product reference image URL for a manual."""
    try:
        conn = _get_connection()
    except RuntimeError:
        return None

    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT product_image_url 
                FROM manuals 
                WHERE id = %s
            """, (manual_id,))
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
    return None


def get_manuals() -> List[dict]:
    """Return all manuals with id, name, and slug for the list endpoint."""
    try:
        conn = _get_connection()
    except RuntimeError:
        return []

    with conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, name, slug FROM manuals ORDER BY id")
            rows = cur.fetchall()
            return [dict(r) for r in rows]


def get_manual(manual_id: int) -> Optional[dict]:
    """Return a single manual by id, or None if not found."""
    try:
        conn = _get_connection()
    except RuntimeError:
        return None

    with conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, slug FROM manuals WHERE id = %s",
                (manual_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_steps_for_manual(manual_id: int) -> List[dict]:
    """Return all steps for a manual (step_number, image_url, description), ordered by step_number."""
    try:
        conn = _get_connection()
    except RuntimeError:
        return []

    with conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT step_number, image_url, description
                FROM steps
                WHERE manual_id = %s
                ORDER BY step_number
                """,
                (manual_id,),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]

def get_pages_for_manual(manual_id: int) -> List[dict]:
    """Return all pages for a manual (page_number, image_url, boxes), ordered by page_number."""
    try:
        conn = _get_connection()
    except RuntimeError:
        return []

    with conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
              """
                SELECT page_number, image_url, suggested_boxes, final_boxes, status
                FROM pages
                WHERE manual_id = %s
                ORDER BY page_number
                """,
               (manual_id,),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        
def update_page_boxes(manual_id: int, page_number: int, boxes: list) -> None:
    """Update bounding boxes for a specific manual page."""
    try:
        conn = _get_connection()
    except RuntimeError:
        return
    
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pages
                SET final_boxes = %s, status = 'CONFIRMED'
                WHERE manual_id = %s AND page_number = %s
                """,
                (psycopg2.extras.Json(boxes), manual_id, page_number),
            )
