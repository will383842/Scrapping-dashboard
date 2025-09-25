# 🕷️ Scraper Pro - Platform de Scraping Web Production-Ready

[![Production Ready](https://img.shields.io/badge/Production-Ready-green.svg)](https://github.com/your-repo/scraper-pro)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue.svg)](https://www.docker.com/)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.38-red.svg)](https://streamlit.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://www.postgresql.org/)

## 🎯 Vue d'Ensemble

Scraper Pro est une **plateforme de scraping web professionnelle** complètement prête pour la production, avec interface moderne, gestion avancée des proxies, monitoring temps réel, et scripts d'automatisation PowerShell.

### ✨ Fonctionnalités Principales

| Fonctionnalité            | Status            | Description                                            |
| ------------------------- | ----------------- | ------------------------------------------------------ |
| 🎨 **Interface Moderne**  | ✅ **Production** | Dashboard Streamlit intuitif avec authentification     |
| 🕷️ **Scraping Avancé**    | ✅ **Production** | Scrapy + Playwright avec JavaScript support            |
| 🌐 **Gestion Proxies**    | ✅ **Production** | Import/export, test automatique, rotation intelligente |
| 📊 **Export Données**     | ✅ **Production** | CSV, Excel, PDF avec formatage professionnel           |
| 📈 **Monitoring**         | ✅ **Production** | Prometheus + Grafana avec alertes                      |
| 🔄 **Backup Auto**        | ✅ **Production** | Sauvegarde programmée avec rétention                   |
| 🔒 **Sécurité**           | ✅ **Production** | SSL, authentification, network isolation               |
| 🚀 **Scripts PowerShell** | ✅ **Production** | Installation et gestion automatisées                   |

---

## 🚀 Installation Rapide (5 minutes)

### Prérequis

- **Windows 10+** avec PowerShell 5.1+
- **Docker Desktop** 4.20+ avec WSL2
- **8GB RAM minimum** (16GB recommandé)

### Installation One-Click

```powershell
# 1. Télécharger le projet
git clone https://github.com/your-repo/scraper-pro.git
cd scraper-pro

# 2. Installation complètement automatisée
.\scripts\setup.ps1

# 3. Accéder au dashboard
# URL: http://localhost:8501
# Credentials affichés à la fin de l'installation
```

**C'est tout !** 🎉 L'installation configure automatiquement :

- ✅ Base de données PostgreSQL optimisée
- ✅ Worker de scraping avec retry automatique
- ✅ Dashboard web sécurisé
- ✅ Monitoring Prometheus/Grafana (optionnel)
- ✅ Scripts de gestion quotidienne

---

## 🎮 Utilisation

### Accès au Dashboard

1. **Ouvrir** http://localhost:8501
2. **Se connecter** avec les credentials générés
3. **Commencer** à créer des jobs de scraping !

### Création d'un Job de Scraping

```
📋 Jobs Manager → ➕ Nouveau Job

URL: https://example.com
Pays: France
Thème: lawyers
Langue: fr
JavaScript: ☑️ (si nécessaire)
Max pages: 25
```

### Gestion des Proxies

```
🌐 Proxy Management → 📝 Proxy Unique

Format supporté:
- IP:PORT
- IP:PORT:USER:PASS
- http://user:pass@ip:port

Import en masse: ✅
Test automatique: ✅
Rotation intelligente: ✅
```

### Export des Données

```
📇 Contacts Explorer → 📊 Export

Formats disponibles:
- CSV avec filtres
- Excel formaté
- PDF professionnel
- Liste emails simple
```

---

## 🔧 Gestion Quotidienne

### Scripts PowerShell Inclus

| Script       | Description            | Exemple                          |
| ------------ | ---------------------- | -------------------------------- |
| `setup.ps1`  | Installation complète  | `.\scripts\setup.ps1`            |
| `manage.ps1` | Gestion quotidienne    | `.\scripts\manage.ps1 status`    |
| `backup.ps1` | Sauvegarde manuelle    | `.\scripts\backup.ps1`           |
| `deploy.ps1` | Déploiement production | `.\scripts\deploy.ps1 -Env prod` |

### Commandes de Base

```powershell
# État du système
.\scripts\manage.ps1 status

# Voir les logs en temps réel
.\scripts\manage.ps1 logs -Follow

# Test de santé complet
.\scripts\manage.ps1 health

# Sauvegarde immédiate
.\scripts\manage.ps1 backup

# Redémarrer tous les services
.\scripts\manage.ps1 restart

# Nettoyer le système
.\scripts\manage.ps1 clean
```

### Monitoring en Temps Réel

- **Dashboard Principal** : http://localhost:8501
- **Prometheus Metrics** : http://localhost:9090
- **Grafana Dashboards** : http://localhost:3000
- **Logs Centralisés** : `.\scripts\manage.ps1 logs`

---

## 📊 Architecture Production

```
┌─────────────────────────────────────────────────────────────┐
│                    SCRAPER PRO PLATFORM                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  Dashboard  │◄──►│   Worker    │◄──►│ PostgreSQL  │     │
│  │ (Streamlit) │    │(Scrapy+PW)  │    │  Database   │     │
│  │ Port: 8501  │    │ Background  │    │ Port: 5432  │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│         ▲                   ▲                   ▲          │
│         │                   │                   │          │
│         ▼                   ▼                   ▼          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │    Nginx    │    │ Prometheus  │    │   Backup    │     │
│  │    SSL      │    │ Monitoring  │    │ Automated   │     │
│  │  Port: 443  │    │ Port: 9090  │    │   Daily     │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                     Docker Network                         │
│                  scraper-pro-internal                      │
└─────────────────────────────────────────────────────────────┘
```

### Composants Principaux

| Composant      | Technologie          | Rôle                  | Port      |
| -------------- | -------------------- | --------------------- | --------- |
| **Dashboard**  | Streamlit            | Interface utilisateur | 8501      |
| **Worker**     | Scrapy + Playwright  | Moteur de scraping    | -         |
| **Database**   | PostgreSQL 15        | Stockage données      | 5432      |
| **Monitoring** | Prometheus + Grafana | Observabilité         | 9090/3000 |
| **Proxy**      | Nginx                | Reverse proxy SSL     | 80/443    |
| **Backup**     | Script PowerShell    | Sauvegarde auto       | -         |

---

## 🔒 Sécurité Production

### Mesures de Sécurité Implémentées

- ✅ **Authentification** : Login/password sécurisés
- ✅ **SSL/TLS** : Certificats automatiques ou Let's Encrypt
- ✅ **Network Isolation** : Réseaux Docker séparés
- ✅ **Rate Limiting** : Protection contre abus
- ✅ **Security Headers** : Protection XSS/CSRF
- ✅ **Audit Logs** : Journalisation complète
- ✅ **Backup Chiffré** : Sauvegardes sécurisées

### Configuration Sécurité

```bash
# .env - Variables de sécurité
FORCE_HTTPS=true
SSL_CERT_PATH=./ssl/fullchain.pem
SSL_KEY_PATH=./ssl/privkey.pem
SESSION_TIMEOUT=3600
MAX_LOGIN_ATTEMPTS=5
AUDIT_LOGS_ENABLED=true
```

---

## 📈 Performance et Monitoring

### Métriques Surveillées

| Catégorie    | Métriques Clés              | Seuils d'Alerte   |
| ------------ | --------------------------- | ----------------- |
| **Jobs**     | Taux succès, durée, queue   | < 80% succès      |
| **Contacts** | Extraction/heure, doublons  | < 100/heure       |
| **Proxies**  | Santé, temps réponse        | < 70% actifs      |
| **Système**  | CPU, RAM, disque            | > 85% utilisation |
| **Database** | Connexions, requêtes lentes | > 80 connexions   |

### Dashboards Grafana Inclus

- 📊 **Overview** : Vue d'ensemble système
- 🎯 **Jobs Performance** : Analyse des tâches
- 📇 **Contact Analytics** : Métriques extraction
- 🌐 **Proxy Health** : Santé des proxies
- 🖥️ **Infrastructure** : Ressources système

### Alertes Automatiques

```yaml
# Exemples d'alertes configurées
- Jobs failure rate > 20%
- No jobs processed for 15min
- Database connections > 80
- Proxy success rate < 70%
- High memory usage > 90%
- Disk space low < 15%
```

---

## 🚀 Déploiement Production

### Environments Supportés

| Environment     | Configuration          | Commande                               |
| --------------- | ---------------------- | -------------------------------------- |
| **Development** | Local, debug enabled   | `.\scripts\setup.ps1 -DevMode`         |
| **Staging**     | Pre-production testing | `.\scripts\deploy.ps1 -Env staging`    |
| **Production**  | Full monitoring, SSL   | `.\scripts\deploy.ps1 -Env production` |

### Déploiement avec Monitoring

```powershell
# Production complète avec monitoring
docker compose --profile production --profile monitoring up -d

# Avec cache Redis
docker compose --profile production --profile cache up -d

# Avec backup automatique
docker compose --profile production --profile backup up -d
```

### Configuration SSL Production

```powershell
# Générer certificats (développement)
.\scripts\generate-ssl.ps1

# Ou utiliser Let's Encrypt (production)
.\scripts\certbot-setup.ps1 -Domain your-domain.com
```

---

## 🧪 Tests et Validation

### Tests Automatisés

```powershell
# Tests complets de validation
python tests/automated_tests.py

# Tests spécifiques
pytest tests/test_worker.py
pytest tests/test_dashboard.py
pytest tests/test_database.py
```

### Validation Production

| Test               | Description                     | Automatique |
| ------------------ | ------------------------------- | ----------- |
| **Infrastructure** | Docker containers, networks     | ✅          |
| **Database**       | Connexions, schéma, performance | ✅          |
| **Dashboard**      | Interface, auth, pages          | ✅          |
| **Worker**         | Processing, heartbeat, errors   | ✅          |
| **API**            | Endpoints, responses            | ✅          |
| **Security**       | SSL, auth, headers              | ✅          |
| **Performance**    | Load times, concurrent users    | ✅          |
| **Monitoring**     | Metrics collection, alerts      | ✅          |

### Health Checks Continus

```powershell
# Test de santé complet
.\scripts\manage.ps1 health

# Résultat exemple:
# 🟢 EXCELLENT - Score: 9/10 (90%)
# ✅ Database: HEALTHY
# ✅ Dashboard: HEALTHY (http://localhost:8501)
# ✅ Worker: ACTIVE (last heartbeat: 1m ago)
# ✅ Proxies: 85% functional (17/20)
```

---

## 📚 Documentation Avancée

### Structure Projet

```
scraper-pro/
├── 📱 dashboard/          # Interface Streamlit
├── 🕷️ scraper/           # Moteur Scrapy
├── ⚙️ orchestration/     # Scheduler worker
├── 🗄️ db/               # Base données
├── 🔧 scripts/          # Automatisation PowerShell
├── 📊 monitoring/       # Prometheus/Grafana
├── 🐳 docker/           # Configuration Docker
├── 🧪 tests/            # Tests automatisés
├── 📖 docs/             # Documentation
└── 🔒 ssl/              # Certificats SSL
```

### Configuration Avancée

| Fichier              | Description             | Modification  |
| -------------------- | ----------------------- | ------------- |
| `.env`               | Variables environnement | ✅ Recommandé |
| `docker-compose.yml` | Services Docker         | ⚠️ Avancé     |
| `prometheus.yml`     | Métriques monitoring    | ⚠️ Avancé     |
| `nginx.conf`         | Reverse proxy           | ⚠️ Expert     |

### Guides Détaillés

- 📖 [**Guide Installation**](docs/INSTALLATION.md)
- 🔧 [**Guide Configuration**](docs/CONFIGURATION.md)
- 🚀 [**Guide Déploiement**](docs/DEPLOYMENT.md)
- 🔒 [**Guide Sécurité**](docs/SECURITY.md)
- 📊 [**Guide Monitoring**](docs/MONITORING.md)
- 🧪 [**Guide Tests**](docs/TESTING.md)

---

## ❓ FAQ et Dépannage

### Questions Fréquentes

<details>
<summary><strong>Q: Comment augmenter les performances de scraping?</strong></summary>

**R:** Plusieurs options :

1. Augmenter `SCRAPY_CONCURRENT_REQUESTS` dans .env
2. Ajouter plus de proxies actifs
3. Optimiser la configuration PostgreSQL
4. Allouer plus de RAM aux containers Docker
</details>

<details>
<summary><strong>Q: Le dashboard est lent, que faire?</strong></summary>

**R:** Vérifications :

1. `.\scripts\manage.ps1 health` - Status général
2. `docker stats` - Utilisation ressources
3. Activer le cache Redis avec `--profile cache`
4. Vérifier les logs : `.\scripts\manage.ps1 logs dashboard`
</details>

<details>
<summary><strong>Q: Comment gérer plusieurs environnements?</strong></summary>

**R:** Créer plusieurs fichiers .env :

```powershell
# Développement
docker compose --env-file .env.dev up -d

# Production
docker compose --env-file .env.prod --profile production up -d
```

</details>

<details>
<summary><strong>Q: Comment sauvegarder et restaurer?</strong></summary>

**R:** Scripts automatiques inclus :

```powershell
# Sauvegarde manuelle
.\scripts\manage.ps1 backup

# Restauration
.\scripts\manage.ps1 restore backup_20241201_143022.zip

# Sauvegarde automatique activée par défaut
```

</details>

### Dépannage Courant

| Problème               | Solution                  | Commande                        |
| ---------------------- | ------------------------- | ------------------------------- |
| Services non démarrés  | Redémarrer Docker Desktop | `.\scripts\manage.ps1 restart`  |
| Dashboard inaccessible | Vérifier port 8501        | `netstat -an \| findstr 8501`   |
| Base données erreur    | Vérifier connexion        | `.\scripts\manage.ps1 logs db`  |
| Worker ne traite pas   | Redémarrer worker         | `docker compose restart worker` |
| Espace disque plein    | Nettoyer système          | `.\scripts\manage.ps1 clean`    |

### Support et Communauté

- 🐛 [**Issues GitHub**](https://github.com/your-repo/scraper-pro/issues)
- 💬 [**Discussions**](https://github.com/your-repo/scraper-pro/discussions)
- 📖 [**Wiki**](https://github.com/your-repo/scraper-pro/wiki)
- 📧 [**Email Support**](mailto:support@scraper-pro.com)

---

## 📋 Changelog

### Version 2.0.0 - Production Ready (2025-01-XX)

#### ✨ Nouveautés Majeures

- 🚀 **Installation One-Click** avec scripts PowerShell
- 📊 **Monitoring Complet** Prometheus + Grafana + Alertes
- 🔒 **Sécurité Production** SSL, authentification, network isolation
- 🔄 **Backup Automatique** avec rétention et restauration
- 🧪 **Tests Automatisés** validation complète du déploiement
- 📈 **Performance Optimisée** base données, cache, workers

#### 🔧 Améliorations Techniques

- Worker avec retry automatique et circuit breakers
- Dashboard moderne avec export Excel/PDF
- Base de données optimisée avec indexes performance
- Docker multi-stage builds pour images légères
- Scripts PowerShell pour Windows Server

#### 🐛 Corrections

- Stabilité worker avec gestion d'erreurs robuste
- Interface dashboard responsive et intuitive
- Gestion mémoire optimisée pour scraping intensif
- Correction des timeouts et reconnections DB

---

## 🏆 Conclusion

**Scraper Pro v2.0** est maintenant **100% production-ready** !

✅ **Installation en 5 minutes**  
✅ **Interface moderne et intuitive**  
✅ **Monitoring et alertes automatiques**  
✅ **Scripts d'automatisation Windows**  
✅ **Sécurité et backup intégrés**  
✅ **Performance optimisée**  
✅ **Tests de validation complets**

Cette plateforme est directement utilisable par votre équipe pour gérer efficacement vos campagnes de scraping web à grande échelle.

---

**Scraper Pro v2.0 - The Complete Web Scraping Solution** 🕷️  
© 2025 - Production Ready Platform
