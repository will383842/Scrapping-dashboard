
import random, time
from typing import List, Dict, Any, Optional
from .redis_coordination import get_redis_client, _ns

def _sticky_key(job_id: Optional[int]) -> str:
    return _ns(f"sticky:{job_id or 'global'}")

def choose(proxies: List[Dict[str, Any]], mode: str = "weighted_random", weights: Optional[Dict[str,float]]=None, job_id: Optional[int]=None, sticky_ttl: int=300) -> Optional[Dict[str, Any]]:
    if not proxies:
        return None
    weights = weights or {}
    if mode == "round_robin":
        r = get_redis_client()
        idx = r.incr(_ns("rr:index")) % len(proxies)
        return proxies[idx]
    if mode == "random":
        return random.choice(proxies)
    if mode == "sticky_session":
        r = get_redis_client()
        key = _sticky_key(job_id)
        idx = r.get(key)
        if idx is not None:
            try:
                return proxies[int(idx) % len(proxies)]
            except Exception:
                pass
        idx = random.randrange(len(proxies))
        r.set(key, str(idx), ex=sticky_ttl)
        return proxies[idx]
    # weighted_random default
    def w(p):
        # weight per label or host, else default 1.0
        return float(weights.get(str(p.get('label') or p.get('host')), weights.get("default", 1.0)))
    choices = [(p, w(p)) for p in proxies]
    total = sum(w for _, w in choices) or 1.0
    pick = random.uniform(0, total)
    acc = 0.0
    for p, wgt in choices:
        acc += wgt
        if pick <= acc:
            return p
    return proxies[-1]
