# -*- coding: utf-8 -*-
from typing import Optional
try:
    from scraper.utils.proxy_selector import select_proxy, mark_proxy_result
except Exception:
    def select_proxy(job_id: Optional[int] = None): return None
    def mark_proxy_result(proxy_id: int, success: bool, error: Optional[str] = None): return None

class RotatingProxyMiddleware:
    def process_request(self, request, spider):
        if request.meta.get("no_proxy"):
            return None
        proxy = select_proxy(job_id=getattr(spider, "query_id", None))
        if not proxy:
            return None
        server = f"{proxy.get('scheme', 'http')}://{proxy['host']}:{proxy['port']}"
        request.meta['proxy'] = server
        if request.meta.get('playwright'):
            auth = {}
            if proxy.get('username'):
                auth = {"username": proxy['username'], "password": proxy.get('password','')}
            request.meta.setdefault('playwright_context_kwargs', {})
            request.meta['playwright_context_kwargs']['proxy'] = {"server": server, **auth}
        request.meta['__current_proxy_id'] = proxy['id']
        return None

    def process_response(self, request, response, spider):
        pid = request.meta.get('__current_proxy_id')
        if pid is not None:
            try: mark_proxy_result(pid, success=True)
            except Exception: pass
        return response

    def process_exception(self, request, exception, spider):
        pid = request.meta.get('__current_proxy_id')
        if pid is not None:
            try: mark_proxy_result(pid, success=False, error=str(exception))
            except Exception: pass
        return None
