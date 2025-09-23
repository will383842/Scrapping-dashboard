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
