import requests
import concurrent.futures

class ProxyWarmer:
    def __init__(self):
        self.warm_urls = [
            "http://httpbin.org/ip",
            "http://httpbin.org/headers", 
            "http://httpbin.org/user-agent",
            "https://www.google.com",
            "https://httpstat.us/200"
        ]
    
    def warm_proxy(self, proxy_config):
        """Réchauffe un proxy avec des requêtes de test"""
        proxy_url = f"{proxy_config['scheme']}://"
        if proxy_config.get('username'):
            proxy_url += f"{proxy_config['username']}:{proxy_config['password']}@"
        proxy_url += f"{proxy_config['host']}:{proxy_config['port']}"
        
        proxies = {'http': proxy_url, 'https': proxy_url}
        success_count = 0
        total_time = 0
        
        for url in self.warm_urls:
            try:
                start = time.time()
                response = requests.get(url, proxies=proxies, timeout=10)
                duration = time.time() - start
                
                if response.status_code == 200:
                    success_count += 1
                    total_time += duration
                    
                time.sleep(random.uniform(1, 3))  # Délai naturel
                
            except Exception:
                pass
        
        # Mettre à jour les stats
        if success_count > 0:
            avg_time = (total_time / success_count) * 1000
            success_rate = success_count / len(self.warm_urls)
            
            execute_query("""
                UPDATE proxies SET 
                    response_time_ms = %s,
                    success_rate = %s,
                    last_test_at = NOW()
                WHERE id = %s
            """, (avg_time, success_rate, proxy_config['id']))
    
    def warm_all_proxies(self):
        """Réchauffe tous les proxies actifs en parallèle"""
        proxies = execute_query("SELECT * FROM proxies WHERE active = true")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(self.warm_proxy, proxies)