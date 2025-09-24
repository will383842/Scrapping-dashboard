
from prometheus_client import Counter, Gauge

SCRAPED_CONTACTS = Counter("scraper_scraped_contacts_total", "Total scraped contacts")
PROXY_FAILURES = Counter("scraper_proxy_failures_total", "Total proxy failures", ["proxy_host"])
ACTIVE_PROXIES = Gauge("scraper_active_proxies", "Number of active proxies")
