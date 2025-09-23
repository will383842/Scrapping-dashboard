# 🚀 Guide de Déploiement Production - Scraper Pro

## Table des Matières

1. [Vue d'Ensemble](#vue-densemble)
2. [Prérequis Système](#prérequis-système)
3. [Installation Rapide](#installation-rapide)
4. [Configuration Avancée](#configuration-avancée)
5. [Déploiement Production](#déploiement-production)
6. [Monitoring et Maintenance](#monitoring-et-maintenance)
7. [Sécurité](#sécurité)
8. [Dépannage](#dépannage)
9. [FAQ](#faq)

---

## Vue d'Ensemble

Scraper Pro est une plateforme de scraping web professionnelle avec dashboard Streamlit, worker Scrapy/Playwright, et base de données PostgreSQL. Cette version 2.0 est entièrement production-ready avec monitoring, backup automatique, et scripts d'automatisation.

### Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Dashboard     │    │     Worker       │    │   PostgreSQL    │
│   (Streamlit)   │◄──►│ (Scrapy+Playwright)│◄──►│   Database      │
│   Port: 8501    │    │   Background     │    │   Port: 5432    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         ▲                        ▲                        ▲
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Network                               │
│                   scraper-pro-internal                         │
└─────────────────────────────────────────────────────────────────┘
```

### Fonctionnalités Clés

- ✅ **Interface Web Moderne** - Dashboard Streamlit intuitif
- ✅ **Scraping Avancé** - Scrapy + Playwright avec JavaScript
- ✅ **Gestion de Proxies** - Import/export, test automatique, rotation
- ✅ **Sessions Authentifiées** - Upload storage states, validation
- ✅ **Export Données** - CSV, Excel, PDF avec formatage
- ✅ **Monitoring Temps Réel** - Métriques, alertes, health checks
- ✅ **Backup Automatique** - Sauvegarde programmée avec rétention
- ✅ **Scripts PowerShell** - Automatisation complète Windows
- ✅ **Production Ready** - SSL, reverse proxy, logging, sécurité

---

## Prérequis Système

### Configuration Minimale

| Composant    | Minimum    | Recommandé  | Production           |
| ------------ | ---------- | ----------- | -------------------- |
| **OS**       | Windows 10 | Windows 11  | Windows Server 2019+ |
| **RAM**      | 8 GB       | 16 GB       | 32 GB+               |
| **CPU**      | 4 cores    | 8 cores     | 16+ cores            |
| **Stockage** | 50 GB SSD  | 100 GB NVMe | 500 GB+ NVMe         |
| **Réseau**   | 100 Mbps   | 1 Gbps      | 10 Gbps              |

### Logiciels Requis

- **Docker Desktop** 4.20+ avec WSL2
- **PowerShell** 5.1+ (Windows PowerShell ou PowerShell 7+)
- **Git** (optionnel, pour le développement)

### Ports Utilisés

| Service    | Port   | Description                |
| ---------- | ------ | -------------------------- |
| Dashboard  | 8501   | Interface web principale   |
| PostgreSQL | 5432   | Base de données            |
| Nginx      | 80/443 | Reverse proxy (production) |
| Prometheus | 9090   | Monitoring (optionnel)     |
| Grafana    | 3000   | Dashboards (optionnel)     |
| Redis      | 6379   | Cache (optionnel)          |

---

## Installation Rapide

### Option 1: Installation Automatisée (Recommandée)

```powershell
# 1. Télécharger ou cloner le projet
git clone https://github.com/your-repo/scraper-pro.git
cd scraper-pro

# 2. Exécuter l'installation automatique
.\scripts\setup.ps1

# 3. Attendre la fin de l'installation (5-10 minutes)
# 4. Ouvrir http://localhost:8501
```

### Option 2: Installation Manuelle

```powershell
# 1. Créer le dossier projet
mkdir C:\scraper-pro
cd C:\scraper-pro

# 2. Copier tous les fichiers du projet

# 3. Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos paramètres

# 4. Construire et démarrer
docker compose up -d

# 5. Vérifier le statut
.\scripts\manage.ps1 status
```

### Vérification Installation

```powershell
# Test de santé complet
.\scripts\manage.ps1 health

# Vérifier les services
docker compose ps

# Accéder au dashboard
start http://localhost:8501
```

---

## Configuration Avancée

### Fichier .env Principal

```bash
# ============================================================================
# CONFIGURATION PRODUCTION SCRAPER PRO
# ============================================================================

# Base de données
POSTGRES_DB=scraper_pro
POSTGRES_USER=scraper_admin
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Dashboard
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=your_dashboard_password
DASHBOARD_PORT=8501

# Sécurité
SECRET_KEY=your_secret_key_32_chars_minimum
JWT_SECRET=your_jwt_secret_key_here
FORCE_HTTPS=true

# Performance
SCRAPY_CONCURRENT_REQUESTS=16
SCRAPY_DOWNLOAD_DELAY=0.5
JS_PAGES_LIMIT=5000
MAX_PAGES_PER_DOMAIN=100
WORKER_TIMEOUT=3600

# Monitoring
ENABLE_MONITORING=true
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
GRAFANA_PASSWORD=admin123

# SSL/TLS
SSL_CERT_PATH=./ssl/fullchain.pem
SSL_KEY_PATH=./ssl/privkey.pem

# Backup
BACKUP_SCHEDULE=daily
BACKUP_RETENTION_DAYS=30
AUTO_BACKUP_ENABLED=true

# Email Alerts
ENABLE_EMAIL_ALERTS=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=alerts@company.com
SMTP_PASSWORD=app_password
ALERT_RECIPIENTS=admin@company.com,devops@company.com
```

### Configuration PostgreSQL Optimisée

Créer `config/postgresql.conf`:

```bash
# Performance
shared_buffers = 1GB                    # 25% de la RAM
effective_cache_size = 3GB              # 75% de la RAM
work_mem = 32MB                         # RAM / max_connections
maintenance_work_mem = 256MB
max_connections = 100

# WAL
wal_buffers = 32MB
checkpoint_completion_target = 0.9
max_wal_size = 2GB
min_wal_size = 512MB

# Query planner
random_page_cost = 1.1
effective_io_concurrency = 200

# Logging
log_statement = 'mod'
log_min_duration_statement = 1000
log_checkpoints = on
log_connections = on
log_disconnections = on
```

### Configuration Nginx Production

Créer `nginx/conf.d/scraper-pro.conf`:

```nginx
# Upstream pour load balancing
upstream dashboard {
    server dashboard:8501 weight=1 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

# HTTP redirect to HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS main server
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000" always;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/css application/javascript application/json;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=dashboard:10m rate=10r/s;

    location / {
        limit_req zone=dashboard burst=20 nodelay;

        proxy_pass http://dashboard;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

---

## Déploiement Production

### 1. Préparation Serveur

```powershell
# Créer utilisateur dédié (optionnel)
net user scraperuser "SecurePassword123!" /add
net localgroup "Users" scraperuser /add

# Créer structure de dossiers
mkdir C:\scraper-pro\{data,logs,backups,ssl,monitoring}
```

### 2. Configuration SSL

```powershell
# Générer certificats auto-signés (développement)
.\scripts\generate-ssl.ps1

# Ou copier certificats Let's Encrypt (production)
copy "C:\Certbot\live\domain.com\fullchain.pem" "ssl\"
copy "C:\Certbot\live\domain.com\privkey.pem" "ssl\"
```

### 3. Déploiement avec Profiles

```powershell
# Production complète avec monitoring
docker compose --profile production --profile monitoring up -d

# Production avec backup automatique
docker compose --profile production --profile backup up -d

# Production + Cache Redis
docker compose --profile production --profile cache up -d
```

### 4. Configuration Firewall Windows

```powershell
# Ouvrir les ports nécessaires
netsh advfirewall firewall add rule name="Scraper Pro HTTP" dir=in action=allow protocol=TCP localport=80
netsh advfirewall firewall add rule name="Scraper Pro HTTPS" dir=in action=allow protocol=TCP localport=443
netsh advfirewall firewall add rule name="Scraper Pro Dashboard" dir=in action=allow protocol=TCP localport=8501
```

### 5. Configuration Windows Service (Optionnel)

Créer `scripts/install-service.ps1`:

```powershell
# Installation comme service Windows avec NSSM
$serviceName = "ScraperPro"
$serviceDescription = "Scraper Pro - Web Scraping Platform"
$workingDir = "C:\scraper-pro"
$executable = "docker"
$arguments = "compose up"

# Télécharger et installer NSSM
$nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
# ... installation NSSM ...

# Créer le service
nssm install $serviceName $executable
nssm set $serviceName Arguments $arguments
nssm set $serviceName AppDirectory $workingDir
nssm set $serviceName Description "$serviceDescription"
nssm set $serviceName Start SERVICE_AUTO_START

# Démarrer le service
net start $serviceName
```

---

## Monitoring et Maintenance

### Dashboard Monitoring

Une fois Prometheus et Grafana activés:

1. **Prometheus**: http://localhost:9090
2. **Grafana**: http://localhost:3000 (admin/admin123)

### Métriques Surveillées

- **Jobs**: Taux de succès, durée moyenne, queue size
- **Contacts**: Extraction rate, déduplication, validation
- **Proxies**: Santé, temps de réponse, rotation
- **Système**: CPU, RAM, disque, réseau
- **Base de données**: Connexions, requêtes lentes, taille

### Alertes Configurées

```yaml
# monitoring/rules/scraper.yml
groups:
  - name: scraper-pro
    rules:
      - alert: JobFailureRate
        expr: rate(scraper_jobs_failed[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Taux d'échec jobs élevé"

      - alert: DatabaseConnections
        expr: postgresql_connections > 80
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Trop de connexions DB"

      - alert: ProxyHealth
        expr: scraper_proxies_healthy / scraper_proxies_total < 0.7
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Moins de 70% des proxies fonctionnels"
```

### Scripts de Maintenance Quotidienne

```powershell
# Tâche programmée Windows
schtasks /create /tn "Scraper Pro Daily Maintenance" /tr "C:\scraper-pro\scripts\daily-maintenance.ps1" /sc daily /st 03:00

# Script daily-maintenance.ps1
.\scripts\manage.ps1 backup
.\scripts\manage.ps1 clean
.\scripts\manage.ps1 health
```

---

## Sécurité

### Checklist Sécurité Production

- [ ] **Mots de passe forts** dans .env (20+ caractères)
- [ ] **SSL/TLS activé** avec certificats valides
- [ ] **Firewall configuré** - ports minimum ouverts
- [ ] **Docker rootless** (optionnel mais recommandé)
- [ ] **Network segmentation** - réseaux Docker séparés
- [ ] **Logs sécurisés** - pas de credentials dans les logs
- [ ] **Backup chiffré** - sauvegarde avec chiffrement
- [ ] **Updates régulières** - images Docker et OS
- [ ] **Monitoring sécurité** - détection d'intrusion
- [ ] **Access control** - authentification renforcée

### Configuration Sécurité Avancée

```bash
# .env - Variables sécurité
SECURITY_LEVEL=high
ENABLE_2FA=true
SESSION_TIMEOUT=3600
MAX_LOGIN_ATTEMPTS=5
BLOCK_DURATION=1800

# Rate limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=3600

# Audit logs
AUDIT_LOGS_ENABLED=true
AUDIT_LOGS_RETENTION=90
```

### Durcissement Docker

```yaml
# docker-compose.override.yml pour production
services:
  dashboard:
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
    user: "1001:1001"

  worker:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

---

## Dépannage

### Problèmes Courants

#### 1. Services ne démarrent pas

```powershell
# Vérifier les logs
.\scripts\manage.ps1 logs

# Vérifier l'espace disque
Get-WmiObject -Class Win32_LogicalDisk | Select-Object DeviceID, @{Name="FreeSpace(GB)";Expression={[math]::Round($_.FreeSpace/1GB,2)}}

# Redémarrer Docker Desktop
Restart-Service docker
```

#### 2. Base de données inaccessible

```powershell
# Tester la connexion
docker compose exec db pg_isready -U scraper_admin -d scraper_pro

# Vérifier les logs DB
docker compose logs db

# Reset base de données (ATTENTION: perte de données)
docker compose down -v
docker compose up -d db
```

#### 3. Dashboard lent ou inaccessible

```powershell
# Vérifier les ressources
docker stats scraper-pro-dashboard

# Redémarrer uniquement le dashboard
docker compose restart dashboard

# Vérifier la configuration Streamlit
docker compose exec dashboard streamlit --version
```

#### 4. Worker n'exécute pas les jobs

```powershell
# Vérifier le scheduler
.\scripts\manage.ps1 stats

# Voir les logs worker en temps réel
docker compose logs -f worker

# Redémarrer le worker
docker compose restart worker
```

### Logs et Debugging

```powershell
# Logs détaillés avec timestamps
docker compose logs --timestamps --follow

# Logs d'un service specifique
docker compose logs worker --tail=100

# Exporter les logs
docker compose logs --no-color > scraper-logs-$(Get-Date -Format 'yyyyMMdd-HHmmss').txt
```

### Recovery Procedures

#### Recovery Base de Données

```powershell
# Restaurer depuis backup automatique
.\scripts\manage.ps1 restore

# Recovery manuel
docker compose down
docker volume rm scraper-pro_pgdata
docker compose up -d db
# Attendre initialisation
docker compose exec -T db psql -U scraper_admin -d scraper_pro < backup.sql
```

#### Recovery Complet Système

```powershell
# Sauvegarde préventive
.\scripts\manage.ps1 backup

# Reset complet avec restauration
docker compose down -v
docker system prune -a -f
.\scripts\setup.ps1 -Force
.\scripts\manage.ps1 restore "backup_file.zip"
```

---

## FAQ

### Q: Puis-je utiliser Scraper Pro sans Docker?

**R**: Non recommandé. Docker garantit la cohérence de l'environnement et simplifie grandement le déploiement. Pour un environnement sans Docker, il faudrait installer manuellement Python, PostgreSQL, et toutes les dépendances.

### Q: Comment augmenter les performances?

**R**:

1. Augmenter `SCRAPY_CONCURRENT_REQUESTS` dans .env
2. Optimiser la configuration PostgreSQL
3. Ajouter plus de RAM aux containers Docker
4. Utiliser des SSD NVMe pour le stockage
5. Activer le cache Redis

### Q: Puis-je déployer sur Linux?

**R**: Les scripts PowerShell sont spécifiques Windows, mais Docker Compose fonctionne sur Linux. Il faudrait adapter les scripts en bash et ajuster quelques configurations.

### Q: Comment gérer plusieurs environnements (dev/staging/prod)?

**R**: Créer plusieurs fichiers .env:

```powershell
# Développement
docker compose --env-file .env.dev up -d

# Production
docker compose --env-file .env.prod --profile production up -d
```

### Q: Comment intégrer avec mon CI/CD?

**R**: Exemple GitLab CI:

```yaml
deploy:
  script:
    - docker compose pull
    - docker compose up -d --force-recreate
    - .\scripts\manage.ps1 health
```

### Q: Combien de proxies puis-je gérer?

**R**: Testé jusqu'à 10,000 proxies. Au-delà, considérer un sharding de la base de données ou un système distribué.

### Q: Les données sont-elles sauvegardées automatiquement?

**R**: Oui, si `AUTO_BACKUP_ENABLED=true`. Sauvegardes quotidiennes par défaut avec rétention de 30 jours.

---

## Support et Ressources

- **Documentation**: [docs/](./docs/)
- **Issues**: [GitHub Issues](https://github.com/your-repo/scraper-pro/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/scraper-pro/discussions)
- **Wiki**: [GitHub Wiki](https://github.com/your-repo/scraper-pro/wiki)

---

**Scraper Pro v2.0** - Production Ready Web Scraping Platform  
© 2025 - Tous droits réservés
