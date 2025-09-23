# ============================================================================
# START.PS1 - Script de Démarrage Simple Scraper Pro
# Version: 2.0 - Démarrage simplifié et sécurisé
# ============================================================================

param(
    [switch]$Build = $false,
    [switch]$Clean = $false,
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Stop"

function Write-Message($Message, $Color = "White") {
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "$timestamp - $Message" -ForegroundColor $Color
}

function Write-Success($Message) { Write-Message $Message "Green" }
function Write-Warning($Message) { Write-Message $Message "Yellow" }
function Write-Error($Message) { Write-Message $Message "Red" }
function Write-Info($Message) { Write-Message $Message "Cyan" }

Write-Host @"
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🕷️ SCRAPER PRO - DÉMARRAGE                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Cyan

# ============================================================================
# VÉRIFICATIONS PRÉLIMINAIRES
# ============================================================================
Write-Info "Vérifications préliminaires..."

# Vérifier Docker
try {
    $dockerVersion = docker --version
    Write-Success "Docker disponible: $dockerVersion"
} catch {
    Write-Error "Docker non disponible. Installez Docker Desktop et redémarrez."
    exit 1
}

# Vérifier les fichiers requis
$requiredFiles = @("docker-compose.yml", ".env")
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Success "✓ $file trouvé"
    } else {
        if ($file -eq ".env") {
            if (Test-Path ".env.example") {
                Write-Info "Création du fichier .env depuis .env.example..."
                Copy-Item ".env.example" ".env"
                Write-Success "✓ Fichier .env créé"
                Write-Warning "⚠️ IMPORTANT: Modifiez le fichier .env avec vos mots de passe!"
            } else {
                Write-Error "✗ Fichiers .env et .env.example manquants"
                exit 1
            }
        } else {
            Write-Error "✗ Fichier requis manquant: $file"
            exit 1
        }
    }
}

# Créer les dossiers nécessaires
$directories = @("logs", "backups", "sessions")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        Write-Success "✓ Dossier $dir créé"
    }
}

# ============================================================================
# NETTOYAGE (si demandé)
# ============================================================================
if ($Clean) {
    Write-Info "Nettoyage des conteneurs existants..."
    try {
        docker compose down --remove-orphans
        Write-Success "✓ Nettoyage terminé"
    } catch {
        Write-Warning "⚠️ Pas de conteneurs à nettoyer"
    }
}

# ============================================================================
# CONSTRUCTION (si demandée)
# ============================================================================
if ($Build) {
    Write-Info "Construction des images Docker..."
    try {
        docker compose build
        Write-Success "✓ Images construites avec succès"
    } catch {
        Write-Error "✗ Erreur lors de la construction des images"
        exit 1
    }
}

# ============================================================================
# DÉMARRAGE DES SERVICES
# ============================================================================
Write-Info "Démarrage des services Scraper Pro..."

try {
    # Démarrage avec logs en cas de verbose
    if ($Verbose) {
        docker compose up -d --remove-orphans
    } else {
        docker compose up -d --remove-orphans 2>$null
    }
    
    Write-Success "✓ Services démarrés avec succès"
    
} catch {
    Write-Error "✗ Erreur lors du démarrage des services: $($_.Exception.Message)"
    Write-Info "Consultez les logs avec: docker compose logs"
    exit 1
}

# ============================================================================
# VÉRIFICATION ET ATTENTE
# ============================================================================
Write-Info "Vérification du démarrage des services..."

# Attente de démarrage (30 secondes)
Write-Info "Attente de l'initialisation (30 secondes)..."
for ($i = 30; $i -gt 0; $i--) {
    Write-Progress -Activity "Initialisation en cours" -Status "$i secondes restantes" -PercentComplete ((30-$i)/30*100)
    Start-Sleep -Seconds 1
}
Write-Progress -Activity "Initialisation en cours" -Completed

# Vérification de l'état des services
Write-Info "État des services:"
try {
    $services = docker compose ps --format "table {{.Name}}\t{{.Status}}"
    Write-Output $services
    
    # Compter les services en cours d'exécution
    $runningServices = (docker compose ps -q | Measure-Object).Count
    
    if ($runningServices -ge 3) {
        Write-Success "✅ Tous les services principaux sont démarrés"
    } else {
        Write-Warning "⚠️ Certains services ne sont pas encore prêts"
    }
    
} catch {
    Write-Warning "⚠️ Impossible de vérifier l'état des services"
}

# Test spécifique de la base de données
Write-Info "Test de la base de données..."
$maxAttempts = 10
$attempt = 0

do {
    $attempt++
    try {
        docker compose exec -T db pg_isready -U scraper_admin -d scraper_pro 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✅ Base de données prête"
            break
        }
    } catch {}
    
    if ($attempt -lt $maxAttempts) {
        Write-Info "Tentative $attempt/$maxAttempts - Attente de la base de données..."
        Start-Sleep -Seconds 3
    }
} while ($attempt -lt $maxAttempts)

if ($attempt -eq $maxAttempts) {
    Write-Warning "⚠️ Base de données non prête après $maxAttempts tentatives"
    Write-Info "Elle peut nécessiter plus de temps pour l'initialisation"
}

# Test du dashboard
Write-Info "Test d'accès au dashboard..."
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8501" -UseBasicParsing -TimeoutSec 10 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Success "✅ Dashboard accessible"
    } else {
        Write-Warning "⚠️ Dashboard répond avec le code: $($response.StatusCode)"
    }
} catch {
    Write-Info "ℹ️ Dashboard pas encore accessible (normal pendant l'initialisation)"
}

# ============================================================================
# INFORMATIONS FINALES
# ============================================================================
Write-Host @"

╔══════════════════════════════════════════════════════════════════════════════╗
║                              🎉 DÉMARRAGE TERMINÉ                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Green

Write-Success "🚀 Scraper Pro démarré avec succès!"

Write-Info "🌐 ACCÈS AU SYSTÈME:"
Write-Info "   Dashboard: http://localhost:8501"
Write-Info "   Credentials: Voir fichier .env (DASHBOARD_USERNAME/DASHBOARD_PASSWORD)"

Write-Info "📋 COMMANDES UTILES:"
Write-Info "   docker compose ps              # Voir l'état des services"
Write-Info "   docker compose logs -f         # Voir les logs en temps réel"
Write-Info "   docker compose down            # Arrêter tous les services"
Write-Info "   .\scripts\quick-fix.ps1 -Status  # Diagnostic rapide"

Write-Info "🔧 DÉPANNAGE:"
Write-Info "   Si des services ne démarrent pas:"
Write-Info "   1. Attendez 2-3 minutes (initialisation)"
Write-Info "   2. Vérifiez: docker compose logs"
Write-Info "   3. Redémarrez: docker compose restart"
Write-Info "   4. En cas de problème: .\scripts\fix-database-issues.ps1"

Write-Success "📚 Le dashboard peut prendre 1-2 minutes pour être complètement fonctionnel"
Write-Info "Accédez à http://localhost:8501 pour commencer à utiliser Scraper Pro!"