
import os
import time
import json
from contextlib import contextmanager
from typing import Optional
import redis

def get_redis_client() -> redis.Redis:
    host = os.getenv("REDIS_HOST", "redis")
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))
    password = os.getenv("REDIS_PASSWORD") or None
    use_ssl = os.getenv("REDIS_USE_SSL", "false").lower() == "true"
    ssl_params = {"ssl": True} if use_ssl else {}
    return redis.Redis(host=host, port=port, db=db, password=password, decode_responses=True, **ssl_params)

def _ns(key: str) -> str:
    ns = os.getenv("REDIS_NAMESPACE", "scraperpro")
    return f"{ns}:{key}"

@contextmanager
def distributed_lock(name: str, ttl: int = 10):
    r = get_redis_client()
    key = _ns(f"lock:{name}")
    token = str(time.time())
    acquired = r.set(key, token, nx=True, ex=ttl)
    try:
        if not acquired:
            yield False
            return
        yield True
    finally:
        # release if token matches
        try:
            v = r.get(key)
            if v == token:
                r.delete(key)
        except Exception:
            pass

def incr_counter(name: str, amount: int = 1) -> int:
    r = get_redis_client()
    return r.incrby(_ns(f"counter:{name}"), amount)

def get_counter(name: str) -> int:
    r = get_redis_client()
    v = r.get(_ns(f"counter:{name}"))
    return int(v) if v else 0

def cache_get(key: str) -> Optional[str]:
    r = get_redis_client()
    return r.get(_ns(f"cache:{key}"))

def cache_set(key: str, value: str, ttl: int = 300):
    r = get_redis_client()
    r.set(_ns(f"cache:{key}"), value, ex=ttl)
