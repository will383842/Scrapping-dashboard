
import os
from typing import Optional, Dict, Any
from .proxy_selector import select_proxy, load_config
from .proxy_failover import report_result
from .redis_coordination import distributed_lock

def acquire_proxy(job_id: Optional[int]=None) -> Optional[Dict[str, Any]]:
    # small lock to avoid stampede
    with distributed_lock("select_proxy", ttl=3) as ok:
        return select_proxy(job_id=job_id)

def to_scrapy_proxy_uri(p: Dict[str, Any]) -> str:
    auth = ""
    if p.get("username"):
        auth = f"{p['username']}:{p.get('password','')}@"
    scheme = p.get("scheme") or "http"
    return f"{scheme}://{auth}{p['host']}:{p['port']}"

def report_proxy_outcome(proxy: Dict[str, Any], success: bool):
    cfg = load_config()
    report_result(proxy, success, cfg.get("circuit_breaker_failures",5), cfg.get("circuit_breaker_cooldown_seconds",600))
