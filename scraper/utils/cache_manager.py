
import json
from typing import Any, Optional
from .redis_coordination import cache_get, cache_set

def get_json(key: str) -> Optional[Any]:
    raw = cache_get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

def set_json(key: str, value: Any, ttl: int = 300):
    cache_set(key, json.dumps(value), ttl)
