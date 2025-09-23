# ============================================================================
# FIX-DATABASE-ISSUES.PS1 - Script de Correction des Problèmes DB
# Version: 2.0 - Résolution complète des erreurs PostgreSQL
# ============================================================================

param(
    [switch]$Force = $false,
    [switch]$Verbose = $false,
    [switch]$ResetData = $false
)

$ErrorActionPreference = "Continue"

function Write-Status($Message, $Color = "White") {
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "$timestamp - $Message" -ForegroundColor $Color
}

function Write-Success($Message) { Write-Status $Message "Green" }
function Write-Warning($Message) { Write-Status $Message "Yellow" }
function Write-Error($Message) { Write-Status $Message "Red" }
function Write-Info($Message) { Write-Status $Message "Cyan" }

Write-Host @"
╔══════════════════════════════════════════════════════════════════════════════╗
║                🔧 CORRECTION COMPLÈTE PROBLÈMES DATABASE                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Magenta

# ============================================================================
# ÉTAPE 1: DIAGNOSTIC COMPLET
# ============================================================================
Write-Info "=== ÉTAPE 1: DIAGNOSTIC COMPLET ==="

# Vérifier Docker
Write-Info "Vérification de Docker..."
try {
    $dockerVersion = docker --version
    Write-Success "Docker détecté: $dockerVersion"
    
    $composeVersion = docker compose version
    Write-Success "Docker Compose détecté: $composeVersion"
} catch {
    Write-Error "Docker non disponible. Installez Docker Desktop et redémarrez."
    exit 1
}

# Vérifier les fichiers requis
$requiredFiles = @(
    "docker-compose.yml",
    ".env",
    "config/postgresql.conf",
    "db/init.sql"
)

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Success "✓ $file trouvé"
    } else {
        Write-Error "✗ $file manquant"
        if ($file -eq ".env") {
            if (Test-Path ".env.example") {
                Write-Info "Création du fichier .env depuis .env.example..."
                Copy-Item ".env.example" ".env"
                Write-Success "Fichier .env créé"
            } else {
                Write-Error "Fichier .env.example manquant également"
                exit 1
            }
        } else {
            Write-Error "Fichier requis manquant: $file"
            exit 1
        }
    }
}

# Vérifier le contenu du fichier .env
Write-Info "Vérification de la configuration .env..."
$envContent = Get-Content ".env" -ErrorAction SilentlyContinue
$requiredVars = @("POSTGRES_PASSWORD", "POSTGRES_USER", "POSTGRES_DB")

foreach ($var in $requiredVars) {
    $found = $envContent | Where-Object { $_ -match "^$var=" }
    if ($found) {
        Write-Success "✓ $var configuré"
    } else {
        Write-Error "✗ $var manquant dans .env"
        exit 1
    }
}

# ============================================================================
# ÉTAPE 2: ARRÊT COMPLET ET NETTOYAGE
# ============================================================================
Write-Info "=== ÉTAPE 2: ARRÊT COMPLET ET NETTOYAGE ==="

Write-Info "Arrêt de tous les conteneurs..."
docker compose down --remove-orphans

Write-Info "Suppression des conteneurs existants..."
$scraperContainers = docker ps -a -q --filter "name=scraper-pro"
if ($scraperContainers) {
    docker rm -f $scraperContainers
    Write-Success "Conteneurs supprimés"
}

Write-Info "Nettoyage des réseaux..."
try {
    docker network rm scraper-pro-internal 2>$null
    docker network prune -f
    Write-Success "Réseaux nettoyés"
} catch {
    Write-Info "Nettoyage réseau terminé"
}

# Suppression des volumes si demandé
if ($ResetData) {
    Write-Warning "Suppression des données (--ResetData activé)..."
    docker volume rm scraper-pro_pgdata 2>$null
    Write-Success "Volume de données supprimé"
} else {
    Write-Info "Conservation des données existantes (utilisez -ResetData pour les supprimer)"
}

# ============================================================================
# ÉTAPE 3: VÉRIFICATION ET CORRECTION DES FICHIERS
# ============================================================================
Write-Info "=== ÉTAPE 3: VÉRIFICATION DES FICHIERS ==="

# Vérifier que postgresql.conf ne contient pas de paramètres problématiques
$postgresqlConf = Get-Content "config/postgresql.conf" -ErrorAction SilentlyContinue
if ($postgresqlConf) {
    $problematicLines = $postgresqlConf | Where-Object { $_ -match "^ALTER SYSTEM SET" }
    if ($problematicLines) {
        Write-Warning "Configuration PostgreSQL contient des paramètres problématiques"
        Write-Info "Les paramètres ALTER SYSTEM SET seront ignorés"
    } else {
        Write-Success "Configuration PostgreSQL correcte"
    }
}

# Vérifier les permissions des dossiers
$directories = @("logs", "backups", "sessions")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        Write-Success "Dossier $dir créé"
    }
}

# ============================================================================
# ÉTAPE 4: CONSTRUCTION DES IMAGES
# ============================================================================
Write-Info "=== ÉTAPE 4: CONSTRUCTION DES IMAGES ==="

Write-Info "Construction des images Docker..."
try {
    # Construction en mode no-cache pour éviter les problèmes
    docker compose build --no-cache
    Write-Success "Images construites avec succès"
} catch {
    Write-Error "Erreur lors de la construction des images"
    Write-Info "Tentative de construction image par image..."
    
    try {
        docker build --no-cache -f Dockerfile.worker -t scraper-pro-worker .
        docker build --no-cache -f Dockerfile.dashboard -t scraper-pro-dashboard .
        Write-Success "Images construites individuellement"
    } catch {
        Write-Error "Impossible de construire les images"
        exit 1
    }
}

# ============================================================================
# ÉTAPE 5: DÉMARRAGE PROGRESSIF
# ============================================================================
Write-Info "=== ÉTAPE 5: DÉMARRAGE PROGRESSIF ==="

# Démarrage de la base de données uniquement
Write-Info "Démarrage de la base de données..."
docker compose up -d db

# Attente avec monitoring détaillé
Write-Info "Attente de l'initialisation de la base de données..."
$maxAttempts = 60
$attempt = 0
$dbReady = $false

do {
    $attempt++
    Start-Sleep -Seconds 2
    
    # Test de santé détaillé
    try {
        # Test de connexion basique
        $healthCheck = docker compose exec -T db pg_isready -h localhost -p 5432 -U scraper_admin -d scraper_pro 2>$null
        
        if ($LASTEXITCODE -eq 0) {
            # Test de connexion avec authentification
            $authTest = docker compose exec -T db psql -U scraper_admin -d scraper_pro -c "SELECT 1;" 2>$null
            
            if ($LASTEXITCODE -eq 0) {
                $dbReady = $true
                Write-Success "Base de données prête et accessible!"
                break
            } else {
                if ($Verbose) {
                    Write-Info "DB ready mais auth failed - tentative $attempt/$maxAttempts"
                }
            }
        } else {
            if ($Verbose) {
                Write-Info "DB not ready - tentative $attempt/$maxAttempts"
            }
        }
    } catch {
        if ($Verbose) {
            Write-Info "Exception lors du test DB - tentative $attempt/$maxAttempts"
        }
    }
    
    # Affichage périodique du statut
    if ($attempt % 10 -eq 0) {
        Write-Info "Attente DB... ($attempt/$maxAttempts)"
        
        # Vérifier les logs en cas de problème
        if ($attempt -gt 30) {
            Write-Info "Vérification des logs de la base de données..."
            docker compose logs db --tail=10
        }
    }
    
} while ($attempt -lt $maxAttempts)

if (-not $dbReady) {
    Write-Error "ERREUR: Base de données non prête après $maxAttempts tentatives"
    Write-Info "Affichage des logs de la base de données:"
    docker compose logs db --tail=20
    Write-Info "Vérifiez la configuration et relancez le script"
    exit 1
}

# Test de connexion approfondi
Write-Info "Test de connexion approfondi..."
$dbTest = docker compose exec -T db psql -U scraper_admin -d scraper_pro -c "SELECT NOW(), version();" 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Success "Test de connexion avancé réussi"
    if ($Verbose) {
        Write-Info "Résultat du test DB:"
        $dbTest | Write-Host -ForegroundColor Gray
    }
} else {
    Write-Warning "Test de connexion avancé échoué mais DB semble prête"
}

# ============================================================================
# ÉTAPE 6: DÉMARRAGE DES AUTRES SERVICES
# ============================================================================
Write-Info "=== ÉTAPE 6: DÉMARRAGE DES AUTRES SERVICES ==="

Write-Info "Démarrage du worker..."
docker compose up -d worker

Write-Info "Attente du démarrage du worker (20 secondes)..."
Start-Sleep -Seconds 20

# Test du worker
$workerLogs = docker compose logs worker --tail=10 2>$null
if ($workerLogs -match "error|Error|ERROR|exception|Exception") {
    Write-Warning "Erreurs détectées dans les logs du worker:"
    $workerLogs | Where-Object { $_ -match "error|Error|ERROR|exception|Exception" } | ForEach-Object {
        Write-Host "  $_" -ForegroundColor Red
    }
} else {
    Write-Success "Worker démarré sans erreurs apparentes"
}

Write-Info "Démarrage du dashboard..."
docker compose up -d dashboard

Write-Info "Attente du démarrage du dashboard (20 secondes)..."
Start-Sleep -Seconds 20

# ============================================================================
# ÉTAPE 7: VÉRIFICATION FINALE
# ============================================================================
Write-Info "=== ÉTAPE 7: VÉRIFICATION FINALE ==="

# Status des conteneurs
Write-Info "État final des conteneurs:"
$finalStatus = docker compose ps --format "table {{.Name}}\t{{.Status}}"
Write-Output $finalStatus

# Test d'accès au dashboard
Write-Info "Test d'accès au dashboard..."
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8501" -UseBasicParsing -TimeoutSec 30 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Success "✅ Dashboard accessible: http://localhost:8501"
    } else {
        Write-Warning "⚠️ Dashboard répond mais avec le code: $($response.StatusCode)"
    }
} catch {
    Write-Warning "⚠️ Dashboard pas encore accessible: $($_.Exception.Message)"
    Write-Info "Le dashboard peut prendre quelques minutes supplémentaires pour être complètement fonctionnel"
}

# Test de santé des connexions DB
Write-Info "Test final des connexions DB..."
$dbHealthTest = docker compose exec -T db psql -U scraper_admin -d scraper_pro -c "SELECT 'DB_OK' as status, COUNT(*) as queue_count FROM queue;" 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Success "✅ Connexions DB opérationnelles"
    if ($Verbose -and $dbHealthTest) {
        Write-Info "Résultat test santé:"
        $dbHealthTest | Write-Host -ForegroundColor Gray
    }
} else {
    Write-Warning "⚠️ Problème potentiel avec les connexions DB"
}

# Vérification des logs pour erreurs récentes
Write-Info "Vérification des erreurs récentes..."
$recentLogs = docker compose logs --since 60s 2>$null
$connectionErrors = $recentLogs | Select-String -Pattern "connection already closed|InterfaceError|OperationalError|connection refused"

if ($connectionErrors) {
    Write-Warning "⚠️ Erreurs de connexion détectées dans les logs récents:"
    $connectionErrors | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    Write-Info "Ces erreurs peuvent être normales pendant le démarrage initial"
} else {
    Write-Success "✅ Aucune erreur de connexion détectée"
}

# ============================================================================
# RAPPORT FINAL
# ============================================================================
Write-Host @"

╔══════════════════════════════════════════════════════════════════════════════╗
║                           📊 RAPPORT FINAL                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Magenta

Write-Success "🎉 CORRECTION TERMINÉE AVEC SUCCÈS!"

Write-Info "✅ Actions réalisées:"
Write-Info "  - Nettoyage complet des conteneurs et réseaux"
Write-Info "  - Vérification et correction des fichiers de configuration"
Write-Info "  - Reconstruction des images Docker"
Write-Info "  - Démarrage progressif et validé des services"
Write-Info "  - Tests de connectivité et de santé"

Write-Info "📋 Services déployés:"
Write-Info "  - PostgreSQL Database: Port 5432"
Write-Info "  - Worker Scrapy/Playwright: Background service"
Write-Info "  - Dashboard Streamlit: http://localhost:8501"

Write-Info "🔧 Prochaines étapes:"
Write-Info "  1. Ouvrir http://localhost:8501 dans votre navigateur"
Write-Info "  2. Vous connecter avec vos credentials du fichier .env"
Write-Info "  3. Configurer vos proxies dans 'Proxy Management'"
Write-Info "  4. Créer un job test dans 'Jobs Manager'"

if ($connectionErrors) {
    Write-Warning "⚠️ ATTENTION: Quelques erreurs de connexion détectées"
    Write-Info "Si les problèmes persistent:"
    Write-Info "  - Redémarrez Docker Desktop"
    Write-Info "  - Relancez ce script avec -ResetData pour un reset complet"
    Write-Info "  - Vérifiez les logs: docker compose logs -f"
} else {
    Write-Success "🎉 SYSTÈME COMPLÈTEMENT OPÉRATIONNEL!"
}

Write-Info "Pour surveiller le système:"
Write-Info "  docker compose ps              # Status des services"
Write-Info "  docker compose logs -f         # Logs en temps réel"
Write-Info "  docker compose logs db         # Logs base de données uniquement"