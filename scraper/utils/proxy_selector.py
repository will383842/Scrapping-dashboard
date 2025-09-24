
import os, json, psycopg2
from typing import List, Dict, Any, Optional
from psycopg2.extras import RealDictCursor
from .proxy_rotation import choose
from .proxy_failover import can_use
from .redis_coordination import _ns
from pathlib import Path

DB=dict(host=os.getenv("POSTGRES_HOST","db"), port=int(os.getenv("POSTGRES_PORT","5432")),
        dbname=os.getenv("POSTGRES_DB","scraper_pro"), user=os.getenv("POSTGRES_USER","scraper_admin"),
        password=os.getenv("POSTGRES_PASSWORD","scraper_admin"))

def load_config() -> Dict[str, Any]:
    cfg_path = Path(os.getenv("PROXY_CONFIG_PATH", "config/proxy_config.json"))
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    return {"rotation_mode":"weighted_random","weights":{"default":1.0},"sticky_ttl_seconds":300,"cooldown_seconds":120,"max_consecutive_failures":3}

def fetch_active_proxies() -> List[Dict[str, Any]]:
    conn=psycopg2.connect(**DB); cur=conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT * FROM proxies
        WHERE active = true AND (cooldown_until IS NULL OR cooldown_until < NOW())
        ORDER BY priority ASC, COALESCE(last_used_at,'1970-01-01') ASC
    """)
    rows=cur.fetchall()
    cur.close(); conn.close()
    return rows

def select_proxy(job_id: Optional[int]=None) -> Optional[Dict[str, Any]]:
    cfg = load_config()
    proxies = [p for p in fetch_active_proxies() if can_use(p)]
    if not proxies:
        return None
    return choose(proxies, mode=cfg.get("rotation_mode","weighted_random"), weights=cfg.get("weights"), job_id=job_id, sticky_ttl=cfg.get("sticky_ttl_seconds",300))
