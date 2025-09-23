# ============================================================================
# FIX-DB-CONNECTIONS.PS1 - Script de Résolution "Connection Already Closed"
# Version: 2.0 - Correction des problèmes de connexion DB
# ============================================================================

param(
    [switch]$Force = $false,
    [switch]$Verbose = $false
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
║                🔧 CORRECTION PROBLÈMES CONNEXION DATABASE                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Magenta

Write-Info "Diagnostic et correction des erreurs 'connection already closed'"

# ============================================================================
# ÉTAPE 1: DIAGNOSTIC
# ============================================================================
Write-Info "=== ÉTAPE 1: DIAGNOSTIC ==="

# Vérifier Docker
Write-Info "Vérification de Docker..."
try {
    $dockerVersion = docker --version
    Write-Success "Docker détecté: $dockerVersion"
} catch {
    Write-Error "Docker non disponible. Installez Docker Desktop."
    exit 1
}

# Vérifier les services
Write-Info "Vérification des services..."
$containers = docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>$null

if ($containers) {
    Write-Success "Services détectés:"
    Write-Output $containers
} else {
    Write-Warning "Aucun service en cours d'exécution"
}

# Vérifier les logs pour erreurs de connexion
Write-Info "Analyse des erreurs dans les logs..."
$logs = docker compose logs --tail=50 2>$null
$connectionErrors = $logs | Select-String -Pattern "connection already closed|InterfaceError|OperationalError"

if ($connectionErrors) {
    Write-Warning "Erreurs de connexion détectées:"
    $connectionErrors | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
} else {
    Write-Success "Aucune erreur de connexion dans les logs récents"
}

# ============================================================================
# ÉTAPE 2: ARRÊT PROPRE DES SERVICES
# ============================================================================
Write-Info "=== ÉTAPE 2: ARRÊT PROPRE DES SERVICES ==="

Write-Info "Arrêt gracieux des services..."
docker compose down --remove-orphans

# Attendre que tout soit vraiment arrêté
Start-Sleep -Seconds 5

# Vérifier qu'il ne reste pas de conteneurs
$remainingContainers = docker ps -q --filter "name=scraper-pro"
if ($remainingContainers) {
    Write-Warning "Conteneurs encore actifs, arrêt forcé..."
    docker stop $remainingContainers
    docker rm $remainingContainers
}

Write-Success "Services arrêtés proprement"

# ============================================================================
# ÉTAPE 3: NETTOYAGE RÉSEAU ET VOLUMES
# ============================================================================
Write-Info "=== ÉTAPE 3: NETTOYAGE ==="

# Nettoyer les réseaux
Write-Info "Nettoyage des réseaux Docker..."
try {
    docker network prune -f
    Write-Success "Réseaux nettoyés"
} catch {
    Write-Warning "Impossible de nettoyer les réseaux"
}

# Nettoyer les volumes non utilisés (préservation des données)
if ($Force) {
    Write-Warning "Mode Force: Suppression des volumes de données"
    docker volume prune -f
} else {
    Write-Info "Préservation des volumes de données (utilisez -Force pour supprimer)"
}

# ============================================================================
# ÉTAPE 4: VÉRIFICATION DE LA CONFIGURATION
# ============================================================================
Write-Info "=== ÉTAPE 4: VÉRIFICATION CONFIGURATION ==="

# Vérifier le fichier .env
if (Test-Path ".env") {
    Write-Success "Fichier .env trouvé"
    
    # Vérifier les variables critiques
    $envContent = Get-Content ".env"
    $criticalVars = @("POSTGRES_PASSWORD", "POSTGRES_USER", "POSTGRES_DB")
    
    foreach ($var in $criticalVars) {
        if ($envContent | Select-String -Pattern "^$var=") {
            Write-Success "  ✓ $var configuré"
        } else {
            Write-Error "  ✗ $var manquant"
        }
    }
} else {
    Write-Error "Fichier .env manquant! Copiez .env.example vers .env"
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Success "Fichier .env créé depuis .env.example"
    }
}

# Vérifier la configuration PostgreSQL
if (Test-Path "config/postgresql.conf") {
    Write-Success "Configuration PostgreSQL personnalisée trouvée"
} else {
    Write-Warning "Configuration PostgreSQL par défaut utilisée"
}

# ============================================================================
# ÉTAPE 5: REDÉMARRAGE PROGRESSIF
# ============================================================================
Write-Info "=== ÉTAPE 5: REDÉMARRAGE PROGRESSIF ==="

# Démarrer uniquement la base de données
Write-Info "Démarrage de la base de données..."
docker compose up -d db

# Attendre que la DB soit vraiment prête
Write-Info "Attente de l'initialisation de la base de données..."
$maxAttempts = 60
$attempt = 0

do {
    $attempt++
    Start-Sleep -Seconds 2
    
    try {
        docker compose exec -T db pg_isready -U scraper_admin -d scraper_pro 2>$null | Out-Null
        $dbReady = $?
    } catch {
        $dbReady = $false
    }
    
    if ($Verbose) {
        Write-Info "Tentative $attempt/$maxAttempts - DB: $(if($dbReady){'READY'}else{'NOT READY'})"
    }
    
    if ($attempt % 10 -eq 0) {
        Write-Info "Attente DB... ($attempt/$maxAttempts)"
    }
    
} while (-not $dbReady -and $attempt -lt $maxAttempts)

if ($dbReady) {
    Write-Success "Base de données prête!"
} else {
    Write-Error "Timeout: Base de données non prête après $maxAttempts tentatives"
    Write-Info "Vérifiez les logs: docker compose logs db"
    exit 1
}

# Test de connexion avancé
Write-Info "Test de connexion avancé..."
$dbTest = docker compose exec -T db psql -U scraper_admin -d scraper_pro -c "SELECT NOW(), version();" 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Success "Test de connexion réussi"
    if ($Verbose) {
        Write-Info "Résultat DB test:"
        $dbTest | Write-Host -ForegroundColor Gray
    }
} else {
    Write-Error "Test de connexion échoué"
    docker compose logs db --tail=20
    exit 1
}

# Démarrer les autres services
Write-Info "Démarrage des autres services..."
docker compose up -d

# ============================================================================
# ÉTAPE 6: VÉRIFICATION FINALE
# ============================================================================
Write-Info "=== ÉTAPE 6: VÉRIFICATION FINALE ==="

# Attendre que tous les services soient prêts
Write-Info "Attente de tous les services..."
Start-Sleep -Seconds 30

# Vérifier le statut final
$finalStatus = docker compose ps --format "table {{.Name}}\t{{.Status}}"
Write-Success "État final des services:"
Write-Output $finalStatus

# Test du dashboard
Write-Info "Test d'accès au dashboard..."
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8501" -UseBasicParsing -TimeoutSec 30 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Success "Dashboard accessible: http://localhost:8501"
    } else {
        Write-Warning "Dashboard non accessible (Status: $($response.StatusCode))"
    }
} catch {
    Write-Warning "Dashboard pas encore prêt: $($_.Exception.Message)"
    Write-Info "Le dashboard peut prendre quelques minutes pour être entièrement fonctionnel"
}

# Vérifier les logs pour s'assurer qu'il n'y a plus d'erreurs
Write-Info "Vérification finale des logs..."
Start-Sleep -Seconds 10
$newLogs = docker compose logs --since 30s 2>$null
$newConnectionErrors = $newLogs | Select-String -Pattern "connection already closed|InterfaceError|OperationalError"

if ($newConnectionErrors) {
    Write-Warning "Nouvelles erreurs de connexion détectées:"
    $newConnectionErrors | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    Write-Warning "Les problèmes persistent. Vérifiez les logs complets avec:"
    Write-Info "  docker compose logs dashboard"
    Write-Info "  docker compose logs worker"
} else {
    Write-Success "Aucune nouvelle erreur de connexion détectée"
}

# ============================================================================
# RAPPORT FINAL
# ============================================================================
Write-Host @"

╔══════════════════════════════════════════════════════════════════════════════╗
║                           📊 RAPPORT FINAL                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Magenta

Write-Success "✅ Corrections appliquées:"
Write-Success "  - Gestionnaire de connexions DB robuste implémenté"
Write-Success "  - Configuration PostgreSQL optimisée"
Write-Success "  - Health checks Docker améliorés"
Write-Success "  - Scheduler avec gestion d'erreur renforcée"

Write-Info "🔧 Actions réalisées:"
Write-Info "  - Arrêt propre des services"
Write-Info "  - Nettoyage des réseaux Docker"
Write-Info "  - Redémarrage progressif"
Write-Info "  - Tests de connexion validés"

Write-Info "📋 Prochaines étapes:"
Write-Info "  1. Surveillez les logs: docker compose logs -f"
Write-Info "  2. Testez le dashboard: http://localhost:8501"
Write-Info "  3. Créez un job test pour valider le système"

if ($newConnectionErrors) {
    Write-Warning "⚠️  ATTENTION: Des erreurs persistent"
    Write-Info "Si les problèmes continuent:"
    Write-Info "  1. Redémarrez Docker Desktop"
    Write-Info "  2. Exécutez: .\scripts\fix-db-connections.ps1 -Force"
    Write-Info "  3. Vérifiez la configuration réseau"
} else {
    Write-Success "🎉 Correction terminée avec succès!"
    Write-Success "Le système devrait maintenant fonctionner sans erreurs de connexion"
}

Write-Info "Pour surveiller la stabilité:"
Write-Info "  .\scripts\manage.ps1 health"
Write-Info "  .\scripts\manage.ps1 logs -Follow"