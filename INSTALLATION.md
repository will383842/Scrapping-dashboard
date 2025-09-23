INSTALLATION_GUIDE = """

# 🚀 GUIDE INSTALLATION COMPLET - SCRAPER PRO

## Prérequis Système

### Minimum Requis:

- **OS**: Windows 10+ (64-bit)
- **RAM**: 8 GB minimum, 16 GB recommandé
- **Processeur**: Intel/AMD 4+ cœurs
- **Espace disque**: 50 GB libre minimum
- **Connexion**: Internet haut débit stable

### Logiciels Requis:

- **Docker Desktop**: Version 4.20+
- **PowerShell**: 5.1+ ou PowerShell Core 7+
- **Navigateur**: Chrome/Edge/Firefox récent

## Installation Automatique (Recommandée)

### Étape 1: Téléchargement

```powershell
# Cloner le repository
git clone https://github.com/your-repo/scraper-pro.git
cd scraper-pro
```

### Étape 2: Installation One-Click

```powershell
# Lance l'installation complète automatique
.\scripts\setup.ps1

# Ou avec options avancées
.\scripts\setup.ps1 -Environment production -Verbose
```

### Étape 3: Vérification

L'installation configure automatiquement:

- ✅ Base PostgreSQL optimisée
- ✅ Worker de scraping avec retry
- ✅ Dashboard web sécurisé
- ✅ Système de proxy rotation
- ✅ Monitoring et alertes

**Temps d'installation**: 5-10 minutes

## Premier Lancement

### Accès Dashboard:

- **URL**: http://localhost:8501
- **Login**: admin
- **Password**: [affiché à la fin de l'installation]

### Test du Système:

```powershell
# Vérifier tous les services
.\scripts\manage.ps1 status

# Test de santé complet
.\scripts\manage.ps1 health
```

## Configuration des Proxies

### Import Rapide:

1. Aller dans "Proxy Management"
2. Cliquer "Import en Masse"
3. Coller vos proxies format: `IP:PORT:USER:PASS`
4. Cliquer "Test Automatique"

### Formats Supportés:

```
192.168.1.1:8080
192.168.1.2:8080:user:pass
http://proxy.example.com:3128
socks5://user:pass@proxy.example.com:1080
```

## Utilisation de Base

### Créer votre Premier Job:

1. **Jobs Manager** → **Nouveau Job**
2. **URL**: https://example.com
3. **Thème**: lawyers (ou autre)
4. **JavaScript**: ☑️ si site dynamique
5. **Cliquer**: "Créer Job"

### Suivre les Résultats:

- **Dashboard**: Vue d'ensemble temps réel
- **Contacts Explorer**: Données extraites
- **Analytics**: Performances et stats

## Maintenance Quotidienne

### Commandes Essentielles:

```powershell
# Status système
.\scripts\manage.ps1 status

# Voir les logs
.\scripts\manage.ps1 logs -Follow

# Sauvegarde
.\scripts\manage.ps1 backup

# Nettoyage
.\scripts\manage.ps1 clean
```

## Dépannage Commun

### Problème: Services ne démarrent pas

**Solution:**

```powershell
# Redémarrer Docker Desktop
Restart-Service docker

# Vérifier ports disponibles
netstat -an | findstr ":8501"

# Redémarrer services
.\scripts\manage.ps1 restart
```

### Problème: Dashboard inaccessible

**Solution:**

```powershell
# Vérifier status
docker compose ps

# Voir logs dashboard
docker compose logs dashboard

# Tester connexion DB
.\scripts\manage.ps1 health
```

### Problème: Pas de contacts extraits

**Vérifications:**

- ✅ Proxies actifs et fonctionnels
- ✅ JavaScript activé si nécessaire
- ✅ Thème et langue corrects
- ✅ Site accessible (test manuel)

## Support et Ressources

- **Documentation**: `docs/` dans le projet
- **Logs**: `logs/` + `.\scripts\manage.ps1 logs`
- **Configuration**: Fichier `.env`
- **Sauvegarde**: `backups/` + commande backup

**Installation réussie = Dashboard accessible + Base données connectée + Jobs qui se traitent**
"""

# 6. ❌ AMÉLIORATION: Guide utilisation simplifié

USAGE_GUIDE = """

# 📖 GUIDE UTILISATION SIMPLE - SCRAPER PRO

## 🎯 Workflow Standard

### 1. Configurer vos Proxies

- **Proxy Management** → **Import en Masse**
- Coller liste proxies (format IP:PORT:USER:PASS)
- **Test Automatique** pour vérifier

### 2. Créer un Job de Scraping

- **Jobs Manager** → **Nouveau Job**
- URL du site à scraper
- Sélectionner **Thème** (lawyers, doctors, etc.)
- Activer **JavaScript** si site dynamique
- **Max pages**: 25-50 pour commencer

### 3. Suivre l'Exécution

- **Dashboard**: Vue d'ensemble temps réel
- Voir jobs **En cours** / **Terminés**
- Surveiller **Taux de succès**

### 4. Récupérer les Données

- **Contacts Explorer** → Voir contacts extraits
- **Export CSV/Excel** pour récupérer données
- Filtrer par pays, thème, date

## 🔧 Réglages Recommandés

### Pour Sites Statiques:

- JavaScript: ❌ Désactivé
- Max pages: 50-100
- Priorité: 10 (normale)

### Pour Sites Dynamiques:

- JavaScript: ✅ Activé
- Max pages: 25-50 (plus lent)
- Session authentifiée si nécessaire

### Pour Sites Protégés:

- Proxies multiples requis
- Session authentifiée recommandée
- JavaScript probablement nécessaire
- Max pages: 15-25 (prudence)

## 📊 Monitoring Performance

### Indicateurs Clés à Surveiller:

- **Taux succès jobs**: >80% = bon
- **Proxies actifs**: >10 recommandé
- **Temps réponse proxies**: <2000ms
- **Contacts/job**: Varie selon site

### Alertes à Surveiller:

- 🚨 Jobs bloqués >2h
- 🔴 Proxies défaillants >50%
- ⚠️ Sessions expirées

## 🛠️ Résolution Problèmes

### Job reste "En cours" longtemps:

1. Vérifier si JavaScript requis
2. Tester URL manuellement
3. Vérifier proxies fonctionnels
4. Redémarrer si bloqué >1h

### Peu/Pas de contacts extraits:

1. Vérifier **thème** correspond au contenu
2. Tester **mots-clés personnalisés**
3. Augmenter **max pages**
4. Vérifier **langue** du site

### Erreurs de proxy:

1. **Test automatique** des proxies
2. Supprimer proxies défaillants
3. Ajouter nouveaux proxies
4. Activer **rotation automatique**

**Conseil**: Commencez avec 1-2 jobs tests avant production
"""
