import sqlite3
from pathlib import Path
from .config import Config

Path(Config.SQLITE_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

def get_conn():
    conn = sqlite3.connect(
        Config.SQLITE_DB_PATH,
        detect_types=sqlite3.PARSE_DECLTYPES
    )
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_task_map (
            lead_id TEXT PRIMARY KEY,
            row_index INTEGER,
            task_key TEXT,
            lead_updated_at TEXT,
            task_updated_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

def upsert_mapping(lead_id, row_index, task_key, lead_updated_at=None, task_updated_at=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO lead_task_map (lead_id, row_index, task_key, lead_updated_at, task_updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(lead_id) DO UPDATE SET
            row_index = excluded.row_index,
            task_key = excluded.task_key,
            lead_updated_at = COALESCE(excluded.lead_updated_at, lead_task_map.lead_updated_at),
            task_updated_at = COALESCE(excluded.task_updated_at, lead_task_map.task_updated_at)
        """,
        (lead_id, row_index, task_key, lead_updated_at, task_updated_at),
    )
    conn.commit()
    conn.close()

def get_mapping_by_lead(lead_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM lead_task_map WHERE lead_id = ?", (lead_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_mappings():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM lead_task_map")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]
