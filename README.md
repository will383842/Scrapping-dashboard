# Multilang Scraper (Prod)
Stack Docker : Streamlit dashboard + worker Scrapy/Playwright + Postgres.

## Démarrage
1. Copier `.env.example` vers `.env` et remplacer les valeurs.
2. `docker compose up -d`
3. Dashboard : http://localhost:8501

## Dev rapide
- `docker compose logs -f worker`
- `docker compose logs -f db`

## Déploiement
- Les secrets restent dans `.env` (non versionné).
- Le schéma DB est dans `db/init.sql`.
