# 📘 User Guide — Usage (EN)

This guide covers: **proxies**, **starting jobs**, **sort/filter/search**, **CSV & SQL exports**, **recipes**, **troubleshooting**.

## Proxies
- **🌐 Proxy Management** → **Import**
- Formats:
```
IP:PORT
IP:PORT:USER:PASS
http://USER:PASS@IP:PORT
https://USER:PASS@HOST:PORT
socks5://USER:PASS@HOST:PORT
```
- **Test** then **Enable** only **OK** rows.
- Settings (⚙️ / `config/proxy_config.json`): `weighted_random`, **Sticky TTL** 120–180s, **RPS** 0.5 (residential) / 1.5 (DC), **Circuit-breaker** 5 → cooldown 90s.

## Start a Job
1. **🎯 Job Manager** → **Create Job**
2. URLs (1/line), Country/Language (optional), JS on/off (Playwright), Concurrency (2–4 with JS / 6–12 no-JS), Delay 0.5–1.5s, Retry 2–3.
3. **🚀 START SCRAPING**.

## Sort / Filter / Search
- **📇 Contacts Explorer** → column sort, filters (country/language/date), full-text search (e.g. `gmail.com`), non-empty fields (email).

## Export
- **⬇️ Export CSV** / **⬇️ Export Emails** (filters considered depending on implementation).
- SQL (psql):
```sql
\copy (SELECT * FROM public.contacts) TO 'contacts.csv' WITH CSV HEADER;
SELECT DISTINCT ON (email) * FROM public.contacts WHERE email IS NOT NULL ORDER BY email, created_at DESC;
```

## Recipes
- **Static**: JS ❌, Concurrency 8–12, Delay ~1s.
- **SPA**: JS ✅, Concurrency 2–4, Delay 1–1.5s, Sticky TTL 180s.

## Troubleshooting
- Dashboard down: `docker compose ps`, `docker logs -f <dashboard>`
- 403/429: Concurrency ↓, Delay ↑, Rotation/Sticky ON, Cooldown, residential pool
- JS timeouts: Timeout ↑, wait-for-selector, try No-JS if HTML fallback.