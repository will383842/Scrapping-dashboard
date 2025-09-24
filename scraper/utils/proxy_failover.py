
import time
from typing import Dict, Any
from .redis_coordination import get_redis_client, _ns
from .circuit_breaker import is_open, record_failure

def can_use(proxy: Dict[str, Any]) -> bool:
    key = f"proxy:{proxy.get('id') or proxy.get('host')}"
    return not is_open(key)

def report_result(proxy: Dict[str, Any], success: bool, max_failures: int, cooldown_seconds: int):
    r = get_redis_client()
    key = _ns(f"proxy:{proxy.get('id') or proxy.get('host')}:fails")
    if success:
        r.delete(key)
    else:
        n = r.incr(key)
        r.expire(key, cooldown_seconds)
        record_failure(f"proxy:{proxy.get('id') or proxy.get('host')}", n, max_failures, cooldown_seconds)
