# Scraper Pro – Guide d’exploitation (Dashboard)

Ce guide couvre :

- Ajout de proxies (IP:PORT, SCHEME://USER:PASS@HOST:PORT, etc.)
- Rotation automatique (priorité, latence, taux de succès)
- Warm‑up (débit initial) – réglage dans Settings
- Déploiement docker et boutons UI (Deploy / ⋮)

## Proxies

**Formats supportés** (un par ligne) :

- `IP:PORT`
- `IP:PORT:USER:PASS`
- `http://IP:PORT`
- `http://USER:PASS@IP:PORT`
- `https://...`, `socks5://...` idem.

Le couple `(scheme,host,port,username)` est unique → importer la même ligne **met à jour** (label, priority, active…).

**Rotation** : le worker doit sélectionner `active=true` en triant par

1. `priority` ASC (1 = priorité maximale),
2. `response_time_ms` ASC,
3. `success_rate` DESC.

Les stats sont mises à jour automatiquement par les tests/batchs. Un proxy qui échoue descend naturellement dans la rotation.

## Warm‑up

But : limiter le débit au démarrage.

- Activer dans **Settings** (DB keys `warmup_enabled`, `warmup_rps`, `warmup_duration_sec`).
- Le worker plafonne les requêtes pendant cette période.

## Docker

```bash
docker compose build dashboard
docker compose up -d db dashboard
docker compose logs -f dashboard
```

Accès : `http://localhost:8501`.

## UI – “Deploy” & menu ⋮

- **Deploy** : lien Streamlit Cloud (sans effet en local Docker).
- **⋮** : Rerun, Clear cache, Theme… Sans impact sur la DB.
