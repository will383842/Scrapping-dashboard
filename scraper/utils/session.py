import os, psycopg2
from psycopg2.extras import RealDictCursor

DB=dict(host=os.getenv("POSTGRES_HOST","db"), port=int(os.getenv("POSTGRES_PORT","5432")),
        dbname=os.getenv("POSTGRES_DB","scraper"), user=os.getenv("POSTGRES_USER","scraper"),
        password=os.getenv("POSTGRES_PASSWORD","scraper"))

def get_storage_state_path(session_id: int):
    if not session_id: return None
    conn=psycopg2.connect(**DB); cur=conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT file_path, active, type FROM sessions WHERE id=%s",(session_id,))
    row=cur.fetchone()
    cur.close(); conn.close()
    if not row or not row.get("active"): return None
    if (row.get("type") or "storage_state") != "storage_state": return None
    p=row["file_path"]
    # Ensure inside mounted /app/sessions
    if not p: return None
    return p if os.path.exists(p) else None
