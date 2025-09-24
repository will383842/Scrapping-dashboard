
import time
from typing import Optional
from .redis_coordination import get_redis_client, _ns

def is_open(key: str) -> bool:
    r = get_redis_client()
    return r.ttl(_ns(f"cb:{key}:open")) > 0

def open_cb(key: str, cooldown_seconds: int):
    r = get_redis_client()
    r.set(_ns(f"cb:{key}:open"), "1", ex=cooldown_seconds)

def record_failure(key: str, failures: int, max_failures: int, cooldown_seconds: int):
    if failures >= max_failures:
        open_cb(key, cooldown_seconds)
