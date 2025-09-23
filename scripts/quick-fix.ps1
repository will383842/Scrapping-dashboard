# ============================================================================
# QUICK-FIX.PS1 - Script de Dépannage Rapide Scraper Pro
# Version: 2.0 - Correction rapide des erreurs communes
# ============================================================================

param(
    [switch]$Restart = $false,
    [switch]$Reset = $false,
    [switch]$Logs = $false,
    [switch]$Status = $false
)

$ErrorActionPreference = "Continue"

function Write-ColorMessage($Message, $Color = "White") {
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "$timestamp - $Message" -ForegroundColor $Color
}

function Write-Success($Message) { Write-ColorMessage $Message "Green" }
function Write-Warning($Message) { Write-ColorMessage $Message "Yellow" }
function Write-Error($Message) { Write-ColorMessage $Message "Red" }
function Write-Info($Message) { Write-ColorMessage $Message "Cyan" }

Write-Host "🔧 SCRAPER PRO - DÉPANNAGE RAPIDE" -ForegroundColor Magenta

# Si aucun paramètre, afficher le status
if (-not ($Restart -or $Reset -or $Logs -or $Status)) {
    $Status = $true
}

# ============================================================================
# STATUS DU SYSTÈME
# ============================================================================
if ($Status) {
    Write-Info "=== STATUS DU SYSTÈME ==="
    
    # Vérifier Docker
    try {
        docker --version | Out-Null
        Write-Success "✅ Docker disponible"
    } catch {
        Write-Error "❌ Docker non disponible"
        exit 1
    }
    
    # Status des conteneurs
    Write-Info "Status des conteneurs:"
    try {
        $containers = docker compose ps --format "table {{.Name}}\t{{.Status}}"
        if ($containers) {
            Write-Output $containers
        } else {
            Write-Warning "⚠️ Aucun conteneur en cours d'exécution"
        }
    } catch {
        Write-Error "❌ Impossible de récupérer le status des conteneurs"
    }
    
    # Test de santé rapide
    Write-Info "Tests de santé:"
    
    # Test DB
    try {
        docker compose exec -T db pg_isready -U scraper_admin -d scraper_pro 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✅ Database: HEALTHY"
        } else {
            Write-Error "❌ Database: UNHEALTHY"
        }
    } catch {
        Write-Error "❌ Database: ERROR"
    }
    
    # Test Dashboard
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8501" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Success "✅ Dashboard: HEALTHY (http://localhost:8501)"
        } else {
            Write-Warning "⚠️ Dashboard: UNHEALTHY"
        }
    } catch {
        Write-Warning "⚠️ Dashboard: UNREACHABLE"
    }
    
    # Erreurs récentes
    Write-Info "Vérification des erreurs récentes..."
    try {
        $recentLogs = docker compose logs --since 5m 2>$null
        $errors = $recentLogs | Select-String -Pattern "error|Error|ERROR|exception|Exception|CRITICAL" | Select-Object -First 3
        
        if ($errors) {
            Write-Warning "⚠️ Erreurs détectées dans les logs récents:"
            foreach ($error in $errors) {
                Write-Host "  $($error.Line.Trim())" -ForegroundColor Red
            }
        } else {
            Write-Success "✅ Aucune erreur critique récente"
        }
    } catch {
        Write-Warning "⚠️ Impossible de vérifier les logs"
    }
}

# ============================================================================
# AFFICHAGE DES LOGS
# ============================================================================
if ($Logs) {
    Write-Info "=== LOGS DU SYSTÈME ==="
    
    Write-Info "Logs des dernières 2 minutes:"
    try {
        docker compose logs --since 2m --timestamps
    } catch {
        Write-Error "❌ Impossible d'afficher les logs"
    }
}

# ============================================================================
# REDÉMARRAGE RAPIDE
# ============================================================================
if ($Restart) {
    Write-Info "=== REDÉMARRAGE RAPIDE ==="
    
    Write-Info "Redémarrage des services..."
    try {
        docker compose restart
        Write-Success "✅ Services redémarrés"
        
        Write-Info "Attente de stabilisation (30 secondes)..."
        Start-Sleep -Seconds 30
        
        # Test rapide
        $dbTest = docker compose exec -T db pg_isready -U scraper_admin -d scraper_pro 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✅ Database opérationnelle après redémarrage"
        } else {
            Write-Warning "⚠️ Database peut nécessiter plus de temps"
        }
        
    } catch {
        Write-Error "❌ Erreur lors du redémarrage"
    }
}

# ============================================================================
# RESET COMPLET
# ============================================================================
if ($Reset) {
    Write-Warning "=== RESET COMPLET ==="
    Write-Warning "ATTENTION: Cette opération va supprimer tous les conteneurs et données!"
    
    $confirmation = Read-Host "Confirmez-vous le reset complet? (tapez 'YES' pour confirmer)"
    
    if ($confirmation -eq "YES") {
        try {
            Write-Info "Arrêt et suppression des conteneurs..."
            docker compose down --volumes --remove-orphans
            
            Write-Info "Suppression des images..."
            docker image rm -f scraper-pro-worker scraper-pro-dashboard 2>$null
            
            Write-Info "Nettoyage Docker..."
            docker system prune -f
            
            Write-Info "Reconstruction et redémarrage..."
            docker compose build --no-cache
            docker compose up -d
            
            Write-Success "✅ Reset complet terminé"
            Write-Info "Le système va prendre quelques minutes pour être complètement opérationnel"
            
        } catch {
            Write-Error "❌ Erreur lors du reset: $($_.Exception.Message)"
        }
    } else {
        Write-Info "Reset annulé"
    }
}

# ============================================================================
# CONSEILS DE DÉPANNAGE
# ============================================================================
if (-not ($Logs -or $Reset)) {
    Write-Info ""
    Write-Info "🔧 CONSEILS DE DÉPANNAGE:"
    Write-Info "  -Status     : Afficher le status détaillé"
    Write-Info "  -Logs       : Afficher les logs récents"
    Write-Info "  -Restart    : Redémarrage rapide des services"
    Write-Info "  -Reset      : Reset complet (ATTENTION: supprime les données)"
    Write-Info ""
    Write-Info "📋 COMMANDES UTILES:"
    Write-Info "  docker compose ps           # Status conteneurs"
    Write-Info "  docker compose logs -f      # Logs en temps réel"
    Write-Info "  docker compose restart db   # Redémarrer uniquement la DB"
    Write-Info "  docker compose down && docker compose up -d  # Redémarrage complet"
    Write-Info ""
    Write-Info "🌐 ACCÈS:"
    Write-Info "  Dashboard: http://localhost:8501"
    Write-Info "  Credentials: Voir fichier .env"
}

Write-Info "Dépannage terminé à $(Get-Date -Format 'HH:mm:ss')"