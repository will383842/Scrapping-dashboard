import random
import time
import threading
from datetime import datetime, timedelta

class ProxyRotator:
    def __init__(self):
        self.current_proxy = None
        self.failed_proxies = set()
        self.proxy_stats = {}
        self.rotation_interval = 300  # 5 minutes
        
    def get_next_proxy(self, country=None):
        """Rotation intelligente des proxies avec scoring"""
        query = """
        SELECT id, scheme, host, port, username, password, success_rate, response_time_ms, last_used_at
        FROM proxies 
        WHERE active = true 
          AND id NOT IN %s
          AND (country_code = %s OR %s IS NULL)
        ORDER BY 
            success_rate DESC,
            response_time_ms ASC,
            last_used_at ASC NULLS FIRST
        LIMIT 5
        """
        
        failed_list = tuple(self.failed_proxies) if self.failed_proxies else (0,)
        proxies = execute_query(query, (failed_list, country, country))
        
        if not proxies:
            # Reset failed proxies si plus aucun disponible
            self.failed_proxies.clear()
            return self.get_next_proxy(country)
        
        # Sélection pondérée basée sur performance
        weights = [p['success_rate'] * (1000 / max(p['response_time_ms'], 100)) for p in proxies]
        selected = random.choices(proxies, weights=weights, k=1)[0]
        
        # Marquer comme utilisé
        execute_query("UPDATE proxies SET last_used_at = NOW() WHERE id = %s", (selected['id'],))
        
        return selected