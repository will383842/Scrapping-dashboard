# ============================================================================
# MANAGE.PS1 - Script de Gestion Quotidienne Scraper Pro
# Version: 2.0 Production-Ready
# Description: Commandes pour la gestion et maintenance quotidienne
# ============================================================================

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "restart", "status", "logs", "backup", "restore", "clean", "update", "health", "stats", "shell", "help")]
    [string]$Action = "help",
    
    [Parameter(Position=1)]
    [string]$Service = "all",
    
    [switch]$Follow = $false,
    [switch]$Verbose = $false,
    [switch]$Force = $false,
    [string]$BackupFile = "",
    [int]$Tail = 50
)

# Configuration
$ErrorActionPreference = "Stop"
$ProjectPath = Get-Location
$BackupPath = Join-Path $ProjectPath "backups"

# Couleurs
$Colors = @{
    Success = "Green"; Warning = "Yellow"; Error = "Red"; Info = "Cyan"; Header = "Magenta"
}

function Write-ColorOutput($Message, $Color, $Prefix = "") {
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "$timestamp $Prefix$Message" -ForegroundColor $Color
}

function Write-Success($Message) { Write-ColorOutput $Message $Colors.Success "✅ " }
function Write-Warning($Message) { Write-ColorOutput $Message $Colors.Warning "⚠️ " }
function Write-Error($Message) { Write-ColorOutput $Message $Colors.Error "❌ " }
function Write-Info($Message) { Write-ColorOutput $Message $Colors.Info "ℹ️ " }
function Write-Header($Message) { Write-ColorOutput $Message $Colors.Header "🚀 " }

# ============================================================================
# GESTION DES SERVICES
# ============================================================================

function Start-Services {
    param([string]$ServiceName = "all")
    
    Write-Header "Démarrage des services"
    
    if ($ServiceName -eq "all") {
        Write-Info "Démarrage de tous les services..."
        docker compose up -d
    } else {
        Write-Info "Démarrage du service: $ServiceName"
        docker compose up -d $ServiceName
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Services démarrés avec succès"
        Start-Sleep -Seconds 3
        Show-Status
    } else {
        Write-Error "Erreur lors du démarrage des services"
    }
}

function Stop-Services {
    param([string]$ServiceName = "all")
    
    Write-Header "Arrêt des services"
    
    if ($ServiceName -eq "all") {
        Write-Info "Arrêt de tous les services..."
        docker compose down
    } else {
        Write-Info "Arrêt du service: $ServiceName"
        docker compose stop $ServiceName
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Services arrêtés avec succès"
    } else {
        Write-Error "Erreur lors de l'arrêt des services"
    }
}

function Restart-Services {
    param([string]$ServiceName = "all")
    
    Write-Header "Redémarrage des services"
    
    if ($ServiceName -eq "all") {
        Write-Info "Redémarrage de tous les services..."
        docker compose restart
    } else {
        Write-Info "Redémarrage du service: $ServiceName"
        docker compose restart $ServiceName
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Services redémarrés avec succès"
        Start-Sleep -Seconds 5
        Show-Status
    } else {
        Write-Error "Erreur lors du redémarrage des services"
    }
}

# ============================================================================
# MONITORING ET STATUS
# ============================================================================

function Show-Status {
    Write-Header "État des services"
    
    try {
        # Status des conteneurs
        $containers = docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>$null
        
        if ($containers) {
            Write-Info "Services Docker:"
            Write-Output $containers | Write-Host -ForegroundColor White
            
            # Vérification santé individuelle
            Write-Info "`nVérification de santé détaillée:"
            
            # Base de données
            try {
                docker compose exec -T db pg_isready -U scraper_admin -d scraper_pro 2>$null | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "Database: HEALTHY"
                } else {
                    Write-Warning "Database: UNHEALTHY"
                }
            } catch {
                Write-Error "Database: ERROR"
            }
            
            # Dashboard
            try {
                $response = Invoke-WebRequest -Uri "http://localhost:8501/_stcore/health" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
                if ($response.StatusCode -eq 200) {
                    Write-Success "Dashboard: HEALTHY (http://localhost:8501)"
                } else {
                    Write-Warning "Dashboard: UNHEALTHY"
                }
            } catch {
                Write-Warning "Dashboard: UNREACHABLE"
            }
            
            # Worker status via database
            try {
                $lastHeartbeat = docker compose exec -T db psql -U scraper_admin -d scraper_pro -c "SELECT value FROM settings WHERE key = 'scheduler_last_heartbeat';" -t 2>$null
                if ($lastHeartbeat -and $lastHeartbeat.Trim()) {
                    $heartbeatTime = [DateTime]::Parse($lastHeartbeat.Trim())
                    $timeDiff = (Get-Date) - $heartbeatTime
                    if ($timeDiff.TotalMinutes -lt 5) {
                        Write-Success "Worker: ACTIVE (last heartbeat: $($timeDiff.Minutes)m ago)"
                    } else {
                        Write-Warning "Worker: STALE (last heartbeat: $($timeDiff.Minutes)m ago)"
                    }
                } else {
                    Write-Warning "Worker: NO HEARTBEAT"
                }
            } catch {
                Write-Warning "Worker: UNKNOWN STATUS"
            }
            
        } else {
            Write-Warning "Aucun service en cours d'exécution"
        }
        
        # Utilisation des ressources
        Show-ResourceUsage
        
    } catch {
        Write-Error "Erreur lors de la récupération du statut: $($_.Exception.Message)"
    }
}

function Show-ResourceUsage {
    Write-Info "`nUtilisation des ressources:"
    
    try {
        $stats = docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" 2>$null
        if ($stats) {
            Write-Output $stats | Write-Host -ForegroundColor Gray
        }
    } catch {
        Write-Warning "Impossible de récupérer les statistiques de ressources"
    }
    
    # Espace disque
    try {
        $drive = Split-Path $ProjectPath -Qualifier
        $disk = Get-WmiObject -Class Win32_LogicalDisk -Filter "DeviceID='$drive'"
        $freeSpaceGB = [math]::Round($disk.FreeSpace / 1GB, 1)
        $totalSpaceGB = [math]::Round($disk.Size / 1GB, 1)
        $usedPercent = [math]::Round(($disk.Size - $disk.FreeSpace) / $disk.Size * 100, 1)
        
        Write-Info "Espace disque: $freeSpaceGB GB libre / $totalSpaceGB GB total ($usedPercent% utilisé)"
    } catch {
        Write-Warning "Impossible de récupérer l'espace disque"
    }
}

# ============================================================================
# LOGS ET DEBUGGING
# ============================================================================

function Show-Logs {
    param(
        [string]$ServiceName = "all",
        [bool]$FollowLogs = $false,
        [int]$TailLines = 50
    )
    
    Write-Header "Affichage des logs"
    
    $logCommand = "docker compose logs"
    
    if ($ServiceName -ne "all") {
        $logCommand += " $ServiceName"
    }
    
    $logCommand += " --tail $TailLines"
    
    if ($FollowLogs) {
        $logCommand += " -f"
        Write-Info "Suivi des logs en temps réel (Ctrl+C pour arrêter)..."
    } else {
        Write-Info "Dernières $TailLines lignes de logs:"
    }
    
    try {
        Invoke-Expression $logCommand
    } catch {
        Write-Error "Erreur lors de l'affichage des logs: $($_.Exception.Message)"
    }
}

# ============================================================================
# STATISTIQUES AVANCÉES
# ============================================================================

function Show-Stats {
    Write-Header "Statistiques détaillées du système"
    
    try {
        # Stats base de données
        $dbStats = docker compose exec -T db psql -U scraper_admin -d scraper_pro -c "
        SELECT 
            'Jobs Total' as metric, COUNT(*)::text as value FROM queue
        UNION ALL
        SELECT 
            'Jobs Pending', COUNT(*)::text FROM queue WHERE status = 'pending'
        UNION ALL
        SELECT 
            'Jobs Done Today', COUNT(*)::text FROM queue WHERE status = 'done' AND DATE(updated_at) = CURRENT_DATE
        UNION ALL
        SELECT 
            'Jobs Failed Today', COUNT(*)::text FROM queue WHERE status = 'failed' AND DATE(updated_at) = CURRENT_DATE
        UNION ALL
        SELECT 
            'Contacts Total', COUNT(*)::text FROM contacts WHERE deleted_at IS NULL
        UNION ALL
        SELECT 
            'Contacts Today', COUNT(*)::text FROM contacts WHERE DATE(created_at) = CURRENT_DATE
        UNION ALL
        SELECT 
            'Proxies Active', COUNT(*)::text FROM proxies WHERE active = true
        UNION ALL
        SELECT 
            'Countries Covered', COUNT(DISTINCT country)::text FROM contacts WHERE country IS NOT NULL;
        " -t 2>$null
        
        if ($dbStats) {
            Write-Info "📊 Métriques Business:"
            $dbStats | Where-Object { $_.Trim() -ne "" -and $_ -notmatch "^\s*$" } | ForEach-Object {
                if ($_ -match '^\s*([^|]+)\|\s*(.+)\s*$') {
                    $metric = $matches[1].Trim()
                    $value = $matches[2].Trim()
                    Write-Host "  $metric`: $value" -ForegroundColor White
                }
            }
        }
        
        # Performance metrics
        Write-Info "`n⚡ Métriques Performance:"
        
        $perfStats = docker compose exec -T db psql -U scraper_admin -d scraper_pro -c "
        SELECT 
            AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_job_duration,
            AVG(contacts_extracted) FILTER (WHERE contacts_extracted > 0) as avg_contacts_per_job,
            COUNT(*) FILTER (WHERE status = 'done') * 100.0 / NULLIF(COUNT(*), 0) as success_rate
        FROM queue 
        WHERE updated_at IS NOT NULL;
        " -t 2>$null
        
        if ($perfStats) {
            $perfStats | Where-Object { $_.Trim() -ne "" -and $_ -notmatch "^\s*$" } | ForEach-Object {
                if ($_ -match '^\s*([^|]+)\|\s*([^|]+)\|\s*(.+)\s*$') {
                    $duration = [math]::Round([double]$matches[1].Trim(), 1)
                    $avgContacts = [math]::Round([double]$matches[2].Trim(), 1)
                    $successRate = [math]::Round([double]$matches[3].Trim(), 1)
                    
                    Write-Host "  Durée moyenne job: ${duration}s" -ForegroundColor White
                    Write-Host "  Contacts/job moyen: $avgContacts" -ForegroundColor White
                    Write-Host "  Taux de succès: ${successRate}%" -ForegroundColor White
                }
            }
        }
        
        # Taille des tables
        Write-Info "`n💾 Utilisation Base de Données:"
        $tableStats = docker compose exec -T db psql -U scraper_admin -d scraper_pro -c "
        SELECT 
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
        FROM pg_tables 
        WHERE schemaname = 'public' 
        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
        " -t 2>$null
        
        if ($tableStats) {
            $tableStats | Where-Object { $_.Trim() -ne "" -and $_ -notmatch "^\s*$" } | ForEach-Object {
                Write-Host "  $_" -ForegroundColor Gray
            }
        }
        
    } catch {
        Write-Error "Erreur lors de la récupération des statistiques: $($_.Exception.Message)"
    }
}

# ============================================================================
# BACKUP ET RESTORE
# ============================================================================

function Backup-System {
    param([string]$BackupName = "")
    
    Write-Header "Sauvegarde du système"
    
    if (-not $BackupName) {
        $BackupName = "backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    }
    
    $backupDir = Join-Path $BackupPath $BackupName
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    
    try {
        # Sauvegarde base de données
        Write-Info "Sauvegarde de la base de données..."
        $dbBackupFile = Join-Path $backupDir "database.sql"
        docker compose exec -T db pg_dump -U scraper_admin -d scraper_pro > $dbBackupFile
        
        if (Test-Path $dbBackupFile -and (Get-Item $dbBackupFile).Length -gt 0) {
            Write-Success "Base de données sauvegardée: $dbBackupFile"
        } else {
            throw "Échec de la sauvegarde de la base de données"
        }
        
        # Sauvegarde configuration
        Write-Info "Sauvegarde des fichiers de configuration..."
        Copy-Item ".env" -Destination (Join-Path $backupDir ".env") -ErrorAction SilentlyContinue
        Copy-Item "docker-compose.yml" -Destination (Join-Path $backupDir "docker-compose.yml") -ErrorAction SilentlyContinue
        
        # Sauvegarde sessions
        if (Test-Path "sessions") {
            Write-Info "Sauvegarde des sessions..."
            Copy-Item "sessions" -Destination (Join-Path $backupDir "sessions") -Recurse -ErrorAction SilentlyContinue
        }
        
        # Création archive ZIP
        Write-Info "Création de l'archive..."
        $zipFile = "$backupDir.zip"
        Compress-Archive -Path $backupDir -DestinationPath $zipFile -Force
        Remove-Item -Path $backupDir -Recurse -Force
        
        $zipSize = [math]::Round((Get-Item $zipFile).Length / 1MB, 1)
        Write-Success "Sauvegarde terminée: $zipFile ($zipSize MB)"
        
        # Nettoyage des anciennes sauvegardes (garde les 10 dernières)
        $oldBackups = Get-ChildItem -Path $BackupPath -Filter "backup_*.zip" | Sort-Object CreationTime -Descending | Select-Object -Skip 10
        if ($oldBackups) {
            Write-Info "Suppression de $($oldBackups.Count) anciennes sauvegardes..."
            $oldBackups | Remove-Item -Force
        }
        
        return $zipFile
        
    } catch {
        Write-Error "Erreur lors de la sauvegarde: $($_.Exception.Message)"
        if (Test-Path $backupDir) {
            Remove-Item -Path $backupDir -Recurse -Force
        }
        return $null
    }
}

function Restore-System {
    param([string]$BackupFilePath)
    
    Write-Header "Restauration du système"
    
    if (-not $BackupFilePath) {
        # Liste les sauvegardes disponibles
        $backups = Get-ChildItem -Path $BackupPath -Filter "backup_*.zip" | Sort-Object CreationTime -Descending
        if ($backups) {
            Write-Info "Sauvegardes disponibles:"
            for ($i = 0; $i -lt $backups.Count; $i++) {
                Write-Host "  [$i] $($backups[$i].Name) - $(Get-Date $backups[$i].CreationTime -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor White
            }
            
            $selection = Read-Host "Sélectionnez une sauvegarde (0-$($backups.Count - 1)) ou 'q' pour annuler"
            if ($selection -eq 'q') {
                Write-Info "Restauration annulée"
                return
            }
            
            if ($selection -match '^\d+$' -and [int]$selection -lt $backups.Count) {
                $BackupFilePath = $backups[[int]$selection].FullName
            } else {
                Write-Error "Sélection invalide"
                return
            }
        } else {
            Write-Error "Aucune sauvegarde trouvée dans $BackupPath"
            return
        }
    }
    
    if (-not (Test-Path $BackupFilePath)) {
        Write-Error "Fichier de sauvegarde non trouvé: $BackupFilePath"
        return
    }
    
    Write-Warning "ATTENTION: Cette opération va écraser les données actuelles!"
    if (-not $Force) {
        $confirm = Read-Host "Confirmez-vous la restauration? (y/N)"
        if ($confirm -ne 'y') {
            Write-Info "Restauration annulée"
            return
        }
    }
    
    try {
        # Arrêt des services
        Write-Info "Arrêt des services..."
        docker compose down
        
        # Extraction de l'archive
        $tempDir = Join-Path $env:TEMP "scraper_restore_$(Get-Date -Format 'HHmmss')"
        Write-Info "Extraction de la sauvegarde..."
        Expand-Archive -Path $BackupFilePath -DestinationPath $tempDir -Force
        
        # Restauration base de données
        Write-Info "Restauration de la base de données..."
        docker compose up -d db
        Start-Sleep -Seconds 10
        
        $dbRestoreFile = Get-ChildItem -Path $tempDir -Filter "database.sql" -Recurse | Select-Object -First 1
        if ($dbRestoreFile) {
            docker compose exec -T db psql -U scraper_admin -d scraper_pro -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
            Get-Content $dbRestoreFile.FullName | docker compose exec -T db psql -U scraper_admin -d scraper_pro
            Write-Success "Base de données restaurée"
        }
        
        # Restauration configuration
        $envFile = Get-ChildItem -Path $tempDir -Filter ".env" -Recurse | Select-Object -First 1
        if ($envFile) {
            Copy-Item $envFile.FullName -Destination ".env" -Force
            Write-Success "Configuration restaurée"
        }
        
        # Restauration sessions
        $sessionsDir = Get-ChildItem -Path $tempDir -Filter "sessions" -Directory -Recurse | Select-Object -First 1
        if ($sessionsDir) {
            if (Test-Path "sessions") {
                Remove-Item "sessions" -Recurse -Force
            }
            Copy-Item $sessionsDir.FullName -Destination "sessions" -Recurse -Force
            Write-Success "Sessions restaurées"
        }
        
        # Redémarrage des services
        Write-Info "Redémarrage des services..."
        docker compose up -d
        
        # Nettoyage
        Remove-Item -Path $tempDir -Recurse -Force
        
        Write-Success "Restauration terminée avec succès!"
        Start-Sleep -Seconds 5
        Show-Status
        
    } catch {
        Write-Error "Erreur lors de la restauration: $($_.Exception.Message)"
        if (Test-Path $tempDir) {
            Remove-Item -Path $tempDir -Recurse -Force
        }
    }
}

# ============================================================================
# NETTOYAGE ET MAINTENANCE
# ============================================================================

function Clean-System {
    Write-Header "Nettoyage du système"
    
    if (-not $Force) {
        Write-Warning "Cette opération va:"
        Write-Info "  - Supprimer les logs anciens (>30 jours)"
        Write-Info "  - Nettoyer les images Docker inutilisées"
        Write-Info "  - Supprimer les anciens jobs terminés (>7 jours)"
        Write-Info "  - Compacter la base de données"
        
        $confirm = Read-Host "Continuer? (y/N)"
        if ($confirm -ne 'y') {
            Write-Info "Nettoyage annulé"
            return
        }
    }
    
    try {
        # Nettoyage base de données
        Write-Info "Nettoyage de la base de données..."
        docker compose exec -T db psql -U scraper_admin -d scraper_pro -c "
        DELETE FROM queue WHERE status IN ('done', 'failed') AND updated_at < NOW() - INTERVAL '7 days';
        DELETE FROM system_logs WHERE timestamp < NOW() - INTERVAL '30 days';
        VACUUM ANALYZE;
        "
        Write-Success "Base de données nettoyée"
        
        # Nettoyage Docker
        Write-Info "Nettoyage des images Docker inutilisées..."
        docker image prune -f
        docker volume prune -f
        Write-Success "Images Docker nettoyées"
        
        # Nettoyage logs
        if (Test-Path "logs") {
            Write-Info "Nettoyage des fichiers de logs..."
            Get-ChildItem -Path "logs" -Filter "*.log" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Force
            Write-Success "Logs anciens supprimés"
        }
        
        Write-Success "Nettoyage terminé avec succès!"
        
    } catch {
        Write-Error "Erreur lors du nettoyage: $($_.Exception.Message)"
    }
}

# ============================================================================
# MISE À JOUR
# ============================================================================

function Update-System {
    Write-Header "Mise à jour du système"
    
    try {
        Write-Info "Sauvegarde automatique avant mise à jour..."
        $backupFile = Backup-System -BackupName "pre_update_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        
        if ($backupFile) {
            Write-Success "Sauvegarde créée: $backupFile"
        } else {
            Write-Warning "Sauvegarde échouée, mais continuation de la mise à jour..."
        }
        
        # Mise à jour des images Docker
        Write-Info "Mise à jour des images Docker..."
        docker compose pull
        
        # Reconstruction des images personnalisées
        Write-Info "Reconstruction des images personnalisées..."
        docker compose build --no-cache
        
        # Redémarrage avec les nouvelles images
        Write-Info "Redémarrage avec les nouvelles images..."
        docker compose up -d --force-recreate
        
        Write-Success "Mise à jour terminée!"
        Start-Sleep -Seconds 10
        Show-Status
        
    } catch {
        Write-Error "Erreur lors de la mise à jour: $($_.Exception.Message)"
        Write-Info "Vous pouvez restaurer la sauvegarde avec: .\manage.ps1 restore"
    }
}

# ============================================================================
# SHELL INTERACTIF
# ============================================================================

function Start-Shell {
    param([string]$ServiceName = "dashboard")
    
    Write-Header "Shell interactif"
    
    $validServices = @("dashboard", "worker", "db")
    if ($ServiceName -notin $validServices) {
        Write-Error "Service invalide. Services disponibles: $($validServices -join ', ')"
        return
    }
    
    Write-Info "Connexion au shell du service: $ServiceName"
    Write-Info "Tapez 'exit' pour quitter"
    
    try {
        if ($ServiceName -eq "db") {
            docker compose exec db psql -U scraper_admin -d scraper_pro
        } else {
            docker compose exec $ServiceName /bin/bash
        }
    } catch {
        Write-Error "Impossible de se connecter au shell: $($_.Exception.Message)"
    }
}

# ============================================================================
# HEALTH CHECK AVANCÉ
# ============================================================================

function Test-Health {
    Write-Header "Test de santé complet du système"
    
    $healthScore = 0
    $maxScore = 10
    
    # Test 1: Services Docker (2 points)
    Write-Info "Test 1: Services Docker..."
    try {
        $runningServices = (docker compose ps -q 2>$null | Measure-Object).Count
        if ($runningServices -ge 3) {
            Write-Success "✅ Tous les services sont en cours d'exécution"
            $healthScore += 2
        } elseif ($runningServices -gt 0) {
            Write-Warning "⚠️ Certains services sont arrêtés"
            $healthScore += 1
        } else {
            Write-Error "❌ Aucun service en cours d'exécution"
        }
    } catch {
        Write-Error "❌ Impossible de vérifier les services Docker"
    }
    
    # Test 2: Base de données (2 points)
    Write-Info "Test 2: Connectivité base de données..."
    try {
        docker compose exec -T db pg_isready -U scraper_admin -d scraper_pro 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✅ Base de données accessible"
            $healthScore += 2
        } else {
            Write-Error "❌ Base de données inaccessible"
        }
    } catch {
        Write-Error "❌ Erreur lors du test de la base de données"
    }
    
    # Test 3: Dashboard web (2 points)
    Write-Info "Test 3: Dashboard web..."
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8501" -UseBasicParsing -TimeoutSec 10 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Success "✅ Dashboard accessible"
            $healthScore += 2
        } else {
            Write-Warning "⚠️ Dashboard non accessible (Status: $($response.StatusCode))"
        }
    } catch {
        Write-Error "❌ Dashboard inaccessible"
    }
    
    # Test 4: Worker heartbeat (2 points)
    Write-Info "Test 4: Worker heartbeat..."
    try {
        $lastHeartbeat = docker compose exec -T db psql -U scraper_admin -d scraper_pro -c "SELECT value FROM settings WHERE key = 'scheduler_last_heartbeat';" -t 2>$null
        if ($lastHeartbeat -and $lastHeartbeat.Trim()) {
            $heartbeatTime = [DateTime]::Parse($lastHeartbeat.Trim())
            $timeDiff = (Get-Date) - $heartbeatTime
            if ($timeDiff.TotalMinutes -lt 5) {
                Write-Success "✅ Worker actif (heartbeat: $([math]::Round($timeDiff.TotalMinutes, 1))m ago)"
                $healthScore += 2
            } else {
                Write-Warning "⚠️ Worker inactif depuis $([math]::Round($timeDiff.TotalMinutes, 1)) minutes"
                $healthScore += 1
            }
        } else {
            Write-Error "❌ Pas de heartbeat worker"
        }
    } catch {
        Write-Error "❌ Impossible de vérifier le worker"
    }
    
    # Test 5: Espace disque et ressources (2 points)
    Write-Info "Test 5: Ressources système..."
    try {
        $drive = Split-Path $ProjectPath -Qualifier
        $disk = Get-WmiObject -Class Win32_LogicalDisk -Filter "DeviceID='$drive'"
        $freeSpaceGB = $disk.FreeSpace / 1GB
        
        if ($freeSpaceGB -gt 5) {
            Write-Success "✅ Espace disque suffisant ($([math]::Round($freeSpaceGB, 1)) GB libre)"
            $healthScore += 2
        } elseif ($freeSpaceGB -gt 1) {
            Write-Warning "⚠️ Espace disque faible ($([math]::Round($freeSpaceGB, 1)) GB libre)"
            $healthScore += 1
        } else {
            Write-Error "❌ Espace disque critique ($([math]::Round($freeSpaceGB, 1)) GB libre)"
        }
    } catch {
        Write-Warning "⚠️ Impossible de vérifier l'espace disque"
    }
    
    # Résultat final
    $healthPercent = ($healthScore / $maxScore) * 100
    Write-Header "RÉSULTAT DU TEST DE SANTÉ"
    
    if ($healthPercent -ge 90) {
        Write-Success "🟢 EXCELLENT - Score: $healthScore/$maxScore ($healthPercent%)"
        Write-Success "Le système fonctionne parfaitement!"
    } elseif ($healthPercent -ge 70) {
        Write-Warning "🟡 BON - Score: $healthScore/$maxScore ($healthPercent%)"
        Write-Warning "Le système fonctionne mais certains éléments nécessitent attention."
    } elseif ($healthPercent -ge 50) {
        Write-Error "🟠 MOYEN - Score: $healthScore/$maxScore ($healthPercent%)"
        Write-Error "Le système a des problèmes qui doivent être résolus."
    } else {
        Write-Error "🔴 CRITIQUE - Score: $healthScore/$maxScore ($healthPercent%)"
        Write-Error "Le système nécessite une intervention immédiate!"
    }
    
    return $healthPercent
}

# ============================================================================
# AIDE
# ============================================================================

function Show-Help {
    Write-Host @"

╔══════════════════════════════════════════════════════════════════════════════╗
║                 🕷️  SCRAPER PRO - GESTION QUOTIDIENNE                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

USAGE:
    .\manage.ps1 <action> [service] [options]

ACTIONS:
    start       Démarre les services (défaut: tous)
    stop        Arrête les services (défaut: tous)  
    restart     Redémarre les services (défaut: tous)
    status      Affiche le statut des services
    logs        Affiche les logs (défaut: tous services, 50 lignes)
    backup      Sauvegarde complète du système
    restore     Restaure une sauvegarde
    clean       Nettoie le système (logs, images Docker, etc.)
    update      Met à jour les images et redémarre
    health      Test de santé complet du système
    stats       Affiche les statistiques détaillées
    shell       Ouvre un shell interactif dans un service
    help        Affiche cette aide

SERVICES:
    all         Tous les services (défaut)
    db          Base de données PostgreSQL
    worker      Worker de scraping
    dashboard   Interface web Streamlit

OPTIONS:
    -Follow             Suit les logs en temps réel (pour logs)
    -Verbose            Affichage détaillé
    -Force              Force l'opération sans confirmation
    -Tail <number>      Nombre de lignes de logs (défaut: 50)
    -BackupFile <path>  Fichier de sauvegarde pour restore

EXEMPLES:
    .\manage.ps1 start                    # Démarre tous les services
    .\manage.ps1 stop worker              # Arrête uniquement le worker
    .\manage.ps1 logs dashboard -Follow   # Suit les logs du dashboard
    .\manage.ps1 backup                   # Sauvegarde complète
    .\manage.ps1 health                   # Test de santé complet
    .\manage.ps1 shell db                 # Shell PostgreSQL
    .\manage.ps1 clean -Force             # Nettoyage sans confirmation

RACCOURCIS:
    .\manage.ps1                         # Affiche le statut
    .\manage.ps1 s                       # status
    .\manage.ps1 l                       # logs

"@ -ForegroundColor Cyan
}

# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

function Main {
    # Vérification que nous sommes dans le bon répertoire
    if (-not (Test-Path "docker-compose.yml")) {
        Write-Error "Ce script doit être exécuté depuis le répertoire du projet (docker-compose.yml non trouvé)"
        exit 1
    }
    
    # Raccourcis
    if ($Action -eq "s") { $Action = "status" }
    if ($Action -eq "l") { $Action = "logs" }
    
    # Exécution de l'action
    switch ($Action) {
        "start"   { Start-Services -ServiceName $Service }
        "stop"    { Stop-Services -ServiceName $Service }
        "restart" { Restart-Services -ServiceName $Service }
        "status"  { Show-Status }
        "logs"    { Show-Logs -ServiceName $Service -FollowLogs $Follow -TailLines $Tail }
        "backup"  { Backup-System | Out-Null }
        "restore" { Restore-System -BackupFilePath $BackupFile }
        "clean"   { Clean-System }
        "update"  { Update-System }
        "health"  { Test-Health | Out-Null }
        "stats"   { Show-Stats }
        "shell"   { Start-Shell -ServiceName $Service }
        "help"    { Show-Help }
        default   { 
            if ($Action -ne "help") {
                Write-Error "Action inconnue: $Action"
            }
            Show-Help 
        }
    }
}

# Point d'entrée
if ($MyInvocation.InvocationName -ne '.') {
    Main
}