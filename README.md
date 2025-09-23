

## Production notes
- Database is not exposed to the internet in `docker-compose.yml`.
- Dashboard requires `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD`.
- Set `JS_PAGES_LIMIT` to cap Playwright usage; it is synced on scheduler boot.
- Consider reverse proxy (Caddy/Traefik) for TLS and network ACLs.
