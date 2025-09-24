
import os, psycopg2
from typing import Optional
from psycopg2.extras import RealDictCursor
from .redis_coordination import get_redis_client, _ns
from .url_normalizer import normalize

DB=dict(host=os.getenv("POSTGRES_HOST","db"), port=int(os.getenv("POSTGRES_PORT","5432")),
        dbname=os.getenv("POSTGRES_DB","scraper_pro"), user=os.getenv("POSTGRES_USER","scraper_admin"),
        password=os.getenv("POSTGRES_PASSWORD","scraper_admin"))

def _redis_key(job_id: Optional[int]) -> str:
    return _ns(f"seen:{job_id or 'global'}")

def is_seen(url: str, job_id: Optional[int]=None) -> bool:
    r = get_redis_client()
    norm = normalize(url)
    return r.sismember(_redis_key(job_id), norm)

def mark_seen(url: str, job_id: Optional[int]=None):
    r = get_redis_client()
    norm = normalize(url)
    r.sadd(_redis_key(job_id), norm)
    # also persist in DB (best-effort)
    try:
        conn=psycopg2.connect(**DB); cur=conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""INSERT INTO seen_urls(url, normalized_url) VALUES(%s,%s)
                     ON CONFLICT (url) DO UPDATE SET last_seen_at=NOW()""", (url, norm))
        conn.commit(); cur.close(); conn.close()
    except Exception:
        pass
