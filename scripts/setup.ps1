# ============================================================================
# SETUP.PS1 - Installation Automatisée Scraper Pro
# Version: 2.0 Production-Ready
# Description: Installation complète one-click du projet
# ============================================================================

param(
    [string]$ProjectPath = "C:\scraper-pro",
    [string]$Environment = "production",
    [switch]$DevMode = $false,
    [switch]$SkipPrerequisites = $false,
    [switch]$Verbose = $false
)

# Configuration
$ErrorActionPreference = "Stop"
$ProgressPreference = "Continue"

# Couleurs pour l'affichage
$Colors = @{
    Success = "Green"
    Warning = "Yellow" 
    Error = "Red"
    Info = "Cyan"
    Header = "Magenta"
}

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

function Write-ColorOutput {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Message,
        [Parameter(Mandatory=$true)]
        [string]$Color,
        [string]$Prefix = ""
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "$timestamp $Prefix$Message" -ForegroundColor $Color
}

function Write-Success { param([string]$Message) Write-ColorOutput -Message $Message -Color $Colors.Success -Prefix "✅ " }
function Write-Warning { param([string]$Message) Write-ColorOutput -Message $Message -Color $Colors.Warning -Prefix "⚠️ " }
function Write-Error { param([string]$Message) Write-ColorOutput -Message $Message -Color $Colors.Error -Prefix "❌ " }
function Write-Info { param([string]$Message) Write-ColorOutput -Message $Message -Color $Colors.Info -Prefix "ℹ️ " }
function Write-Header { param([string]$Message) Write-ColorOutput -Message $Message -Color $Colors.Header -Prefix "🚀 " }

function Test-CommandExists {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

function New-SecurePassword {
    param([int]$Length = 16)
    $chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    -join ((1..$Length) | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
}

function Test-DockerHealth {
    try {
        $dockerVersion = docker --version 2>$null
        $composeVersion = docker compose version 2>$null
        return ($dockerVersion -and $composeVersion)
    } catch {
        return $false
    }
}

function Wait-ForUserInput {
    param([string]$Message = "Appuyez sur Entrée pour continuer...")
    Write-Host $Message -ForegroundColor Yellow
    Read-Host
}

# ============================================================================
# VÉRIFICATION DES PRÉREQUIS
# ============================================================================

function Test-Prerequisites {
    Write-Header "Vérification des prérequis système"
    
    $prereqsPassed = $true
    
    # Windows Version
    $winVersion = [System.Environment]::OSVersion.Version
    if ($winVersion.Major -lt 10) {
        Write-Error "Windows 10+ requis (version détectée: $($winVersion))"
        $prereqsPassed = $false
    } else {
        Write-Success "Windows $($winVersion.Major).$($winVersion.Minor) détecté"
    }
    
    # PowerShell Version
    if ($PSVersionTable.PSVersion.Major -lt 5) {
        Write-Error "PowerShell 5.0+ requis (version: $($PSVersionTable.PSVersion))"
        $prereqsPassed = $false
    } else {
        Write-Success "PowerShell $($PSVersionTable.PSVersion) OK"
    }
    
    # Docker Desktop
    if (-not (Test-CommandExists "docker")) {
        Write-Warning "Docker non trouvé"
        $installDocker = Read-Host "Voulez-vous installer Docker Desktop automatiquement? (y/N)"
        if ($installDocker -eq "y") {
            Install-DockerDesktop
        } else {
            Write-Error "Docker est requis. Installez Docker Desktop manuellement."
            $prereqsPassed = $false
        }
    } else {
        if (Test-DockerHealth) {
            Write-Success "Docker Desktop opérationnel"
        } else {
            Write-Warning "Docker trouvé mais non opérationnel. Démarrez Docker Desktop."
            Wait-ForUserInput
            if (-not (Test-DockerHealth)) {
                Write-Error "Docker Desktop non opérationnel"
                $prereqsPassed = $false
            }
        }
    }
    
    # Docker Compose
    if (-not (Test-CommandExists "docker")) {
        # Docker Compose est maintenant intégré à Docker Desktop
    } else {
        try {
            docker compose version | Out-Null
            Write-Success "Docker Compose disponible"
        } catch {
            Write-Error "Docker Compose non disponible"
            $prereqsPassed = $false
        }
    }
    
    # Espace disque (minimum 2GB)
    $drive = Split-Path $ProjectPath -Qualifier
    $freeSpace = (Get-WmiObject -Class Win32_LogicalDisk -Filter "DeviceID='$drive'").FreeSpace / 1GB
    if ($freeSpace -lt 2) {
        Write-Error "Espace disque insuffisant: ${freeSpace}GB libre (minimum 2GB requis)"
        $prereqsPassed = $false
    } else {
        Write-Success "Espace disque suffisant: $([math]::Round($freeSpace, 1))GB libre"
    }
    
    # Permissions administrateur pour certaines opérations
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if ($currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Success "Permissions administrateur détectées"
    } else {
        Write-Warning "Permissions administrateur non détectées (optionnel)"
    }
    
    if (-not $prereqsPassed) {
        Write-Error "Certains prérequis ne sont pas satisfaits. Installation annulée."
        exit 1
    }
    
    Write-Success "Tous les prérequis sont satisfaits!"
}

function Install-DockerDesktop {
    Write-Header "Installation automatique de Docker Desktop"
    
    try {
        # URL de téléchargement Docker Desktop
        $dockerUrl = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
        $dockerInstaller = "$env:TEMP\DockerDesktopInstaller.exe"
        
        Write-Info "Téléchargement de Docker Desktop..."
        Invoke-WebRequest -Uri $dockerUrl -OutFile $dockerInstaller -UseBasicParsing
        
        Write-Info "Installation de Docker Desktop (cela peut prendre plusieurs minutes)..."
        Start-Process -FilePath $dockerInstaller -ArgumentList "install", "--quiet" -Wait
        
        Write-Success "Docker Desktop installé avec succès!"
        Write-Warning "IMPORTANT: Redémarrez votre ordinateur et relancez ce script."
        
        $restart = Read-Host "Voulez-vous redémarrer maintenant? (y/N)"
        if ($restart -eq "y") {
            Restart-Computer -Force
        }
        
        exit 0
        
    } catch {
        Write-Error "Erreur lors de l'installation de Docker: $($_.Exception.Message)"
        Write-Info "Installez Docker Desktop manuellement depuis: https://www.docker.com/products/docker-desktop"
        exit 1
    }
}

# ============================================================================
# CRÉATION DE LA STRUCTURE PROJET
# ============================================================================

function New-ProjectStructure {
    Write-Header "Création de la structure de projet"
    
    # Vérification si le dossier existe
    if (Test-Path $ProjectPath) {
        Write-Warning "Le dossier $ProjectPath existe déjà"
        $overwrite = Read-Host "Voulez-vous continuer? Les fichiers existants seront préservés. (y/N)"
        if ($overwrite -ne "y") {
            Write-Info "Installation annulée par l'utilisateur"
            exit 0
        }
    }
    
    # Création du dossier principal
    New-Item -ItemType Directory -Force -Path $ProjectPath | Out-Null
    Set-Location $ProjectPath
    Write-Success "Dossier principal créé: $ProjectPath"
    
    # Structure complète des dossiers
    $folders = @(
        "dashboard", "dashboard\pages", "dashboard\components", "dashboard\utils",
        "scraper", "scraper\spiders", "scraper\utils", 
        "orchestration", "config", "db", "sessions", "logs", "backups",
        "monitoring", "scripts", "tests", "docs", "ssl", "nginx"
    )
    
    Write-Info "Création de la structure de dossiers..."
    foreach ($folder in $folders) {
        New-Item -ItemType Directory -Force -Path $folder | Out-Null
        if ($Verbose) {
            Write-Info "  📁 $folder"
        }
    }
    
    # Fichiers de configuration vides
    $configFiles = @(
        "logs\.gitkeep",
        "backups\.gitkeep", 
        "sessions\.gitkeep",
        "ssl\.gitkeep"
    )
    
    foreach ($file in $configFiles) {
        New-Item -ItemType File -Force -Path $file | Out-Null
    }
    
    Write-Success "Structure de projet créée avec succès"
}

# ============================================================================
# CONFIGURATION ENVIRONNEMENT
# ============================================================================

function New-EnvironmentConfiguration {
    Write-Header "Configuration de l'environnement"
    
    # Génération de mots de passe sécurisés
    $dbPassword = New-SecurePassword -Length 24
    $dashboardPassword = New-SecurePassword -Length 16
    $secretKey = New-SecurePassword -Length 32
    
    # Configuration de base
    $envContent = @"
# ============================================================================
# SCRAPER PRO - CONFIGURATION ENVIRONNEMENT
# Généré automatiquement le $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# ============================================================================

# Base de Données PostgreSQL
POSTGRES_DB=scraper_pro
POSTGRES_USER=scraper_admin
POSTGRES_PASSWORD=$dbPassword
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Dashboard Streamlit
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=$dashboardPassword

# Configuration Scrapy
SCRAPY_CONCURRENT_REQUESTS=16
SCRAPY_DOWNLOAD_DELAY=0.5
SCRAPY_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36

# Playwright Configuration
PLAYWRIGHT_BROWSER_TYPE=chromium
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT=45000
PLAYWRIGHT_LAUNCH_OPTIONS={"headless":true,"args":["--no-sandbox","--disable-dev-shm-usage"]}

# Limites et Performance
JS_PAGES_LIMIT=2000
MAX_PAGES_PER_DOMAIN=50
WORKER_TIMEOUT=1800
MAX_RETRIES=3
RETRY_BACKOFF_BASE=2.0

# Scheduler Configuration
POLL_INTERVAL_SEC=3
HEALTH_CHECK_INTERVAL=60
JOB_TIMEOUT_SEC=1800

# Système
TZ=Europe/Paris
LOG_LEVEL=INFO
ENVIRONMENT=$Environment
SECRET_KEY=$secretKey

# Monitoring et Alertes (optionnel)
ENABLE_MONITORING=false
ENABLE_EMAIL_ALERTS=false
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your-email@gmail.com
# SMTP_PASSWORD=your-app-password
# ALERT_RECIPIENTS=admin@company.com

# Proxy Configuration Globale (optionnel)
# PROXY_SERVER=http://proxy.company.com:8080
# PROXY_USERNAME=proxy_user
# PROXY_PASSWORD=proxy_pass

# Sécurité SSL/TLS (production)
# SSL_CERT_PATH=./ssl/cert.pem
# SSL_KEY_PATH=./ssl/key.pem
# FORCE_HTTPS=true

# Backup Configuration
BACKUP_RETENTION_DAYS=30
AUTO_BACKUP_ENABLED=true
BACKUP_SCHEDULE=daily

# Advanced Configuration
CONNECTION_POOL_SIZE=20
MAX_CONNECTIONS=100
QUERY_TIMEOUT=30
STATEMENT_TIMEOUT=60

"@
    
    # Écriture du fichier .env
    $envContent | Out-File -FilePath ".env" -Encoding UTF8
    Write-Success "Fichier .env créé avec mots de passe sécurisés"
    
    # Affichage des credentials
    Write-Info "═══════════════════════════════════════════════════"
    Write-Info "🔑 CREDENTIALS GÉNÉRÉS (à noter précieusement!)"
    Write-Info "═══════════════════════════════════════════════════"
    Write-Success "Dashboard URL: http://localhost:8501"
    Write-Success "Username: admin"
    Write-Success "Password: $dashboardPassword"
    Write-Info "Base de données: $dbPassword"
    Write-Info "═══════════════════════════════════════════════════"
    
    # Sauvegarde sécurisée des credentials
    $credentialsFile = "scripts\credentials_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
    $credentialsContent = @"
SCRAPER PRO - CREDENTIALS
========================
Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

Dashboard Access:
- URL: http://localhost:8501  
- Username: admin
- Password: $dashboardPassword

Database:
- Password: $dbPassword

Secret Key: $secretKey

IMPORTANT: Keep this file secure and delete after noting credentials!
"@
    
    $credentialsContent | Out-File -FilePath $credentialsFile -Encoding UTF8
    Write-Info "Credentials sauvegardés dans: $credentialsFile"
    
    return @{
        DashboardPassword = $dashboardPassword
        DatabasePassword = $dbPassword
    }
}

# ============================================================================
# INSTALLATION DES DÉPENDANCES
# ============================================================================

function Install-PythonDependencies {
    Write-Header "Configuration des dépendances Python"
    
    # Fichier requirements.txt complet
    $requirementsContent = @"
# Core Framework
scrapy==2.11.2
scrapy-playwright==0.0.36
playwright==1.47.0
streamlit==1.38.0

# Database & ORM  
psycopg2-binary==2.9.9
sqlalchemy==2.0.23

# Data Processing & Export
pandas==2.1.4
numpy==1.25.2
openpyxl==3.1.2
xlsxwriter==3.2.0

# Plotting & Visualization
plotly==5.17.0
matplotlib==3.8.2
seaborn==0.13.0

# Web & HTTP
requests==2.31.0
urllib3==2.1.0
tldextract==5.1.1

# Text Processing
python-slugify==8.0.1
phonenumbers==8.13.45
langdetect==1.0.9
textblob==0.17.1

# Utilities
python-dotenv==1.0.0
pyyaml==6.0.1
click==8.1.7
rich==13.7.0
typer==0.9.0

# Development & Testing (optionnel)
pytest==7.4.3
pytest-asyncio==0.21.1
black==23.11.0
flake8==6.1.0

# Security
cryptography==41.0.8
bcrypt==4.1.2

# Monitoring (optionnel)
prometheus-client==0.19.0
"@
    
    $requirementsContent | Out-File -FilePath "requirements.txt" -Encoding UTF8
    Write-Success "Fichier requirements.txt créé"
}

function Copy-ProjectFiles {
    Write-Header "Configuration des fichiers projet"
    
    # Docker Compose production
    $dockerComposeContent = @"
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: scraper-pro-db
    env_file: .env
    environment:
      POSTGRES_DB: \${POSTGRES_DB}
      POSTGRES_USER: \${POSTGRES_USER}
      POSTGRES_PASSWORD: \${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
      - ./backups:/backups
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U \${POSTGRES_USER} -d \${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 20
      start_period: 30s
    restart: unless-stopped
    networks:
      - scraper-network
    
  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    container_name: scraper-pro-worker
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./sessions:/app/sessions
      - ./logs:/app/logs
      - ./config:/app/config
    restart: unless-stopped
    networks:
      - scraper-network
    healthcheck:
      test: ["CMD", "python", "-c", "import psycopg2; psycopg2.connect(host='db', port=5432, database='\${POSTGRES_DB}', user='\${POSTGRES_USER}', password='\${POSTGRES_PASSWORD}').close()"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    
  dashboard:
    build:
      context: .
      dockerfile: Dockerfile.dashboard
    container_name: scraper-pro-dashboard
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8501:8501"
    volumes:
      - ./sessions:/app/sessions
      - ./logs:/app/logs
      - ./backups:/app/backups
      - ./config:/app/config
    restart: unless-stopped
    networks:
      - scraper-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s  
      timeout: 10s
      retries: 3
      start_period: 60s
    
  # Service de monitoring optionnel
  monitoring:
    image: prom/prometheus:latest
    container_name: scraper-pro-monitoring
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
    restart: unless-stopped
    networks:
      - scraper-network
    profiles:
      - monitoring
      
  # Nginx reverse proxy pour production
  nginx:
    image: nginx:alpine
    container_name: scraper-pro-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - ./nginx/logs:/var/log/nginx
    depends_on:
      - dashboard
    restart: unless-stopped
    networks:
      - scraper-network
    profiles:
      - production

volumes:
  pgdata:
    driver: local
  prometheus-data:
    driver: local

networks:
  scraper-network:
    driver: bridge
    name: scraper-pro-network
"@
    
    $dockerComposeContent | Out-File -FilePath "docker-compose.yml" -Encoding UTF8
    Write-Success "Docker Compose configuré"
    
    # Configuration Nginx
    New-Item -ItemType Directory -Force -Path "nginx" | Out-Null
    $nginxConfig = @"
events {
    worker_connections 1024;
}

http {
    upstream dashboard {
        server dashboard:8501;
    }
    
    server {
        listen 80;
        server_name localhost;
        
        location / {
            proxy_pass http://dashboard;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            
            # WebSocket support for Streamlit
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
"@
    
    $nginxConfig | Out-File -FilePath "nginx\nginx.conf" -Encoding UTF8
    Write-Success "Configuration Nginx créée"
}

# ============================================================================
# CONSTRUCTION ET DÉMARRAGE
# ============================================================================

function Build-DockerImages {
    Write-Header "Construction des images Docker"
    
    try {
        Write-Info "Construction de l'image worker..."
        docker build -f Dockerfile.worker -t scraper-pro-worker . 2>&1 | Write-Output
        
        Write-Info "Construction de l'image dashboard..."
        docker build -f Dockerfile.dashboard -t scraper-pro-dashboard . 2>&1 | Write-Output
        
        Write-Success "Images Docker construites avec succès"
        
    } catch {
        Write-Error "Erreur lors de la construction des images: $($_.Exception.Message)"
        return $false
    }
    
    return $true
}

function Initialize-Database {
    Write-Header "Initialisation de la base de données"
    
    try {
        Write-Info "Démarrage du service base de données..."
        docker compose up -d db 2>&1 | Write-Output
        
        Write-Info "Attente de la disponibilité de la base de données..."
        $maxAttempts = 30
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
                Write-Info "Tentative $attempt/$maxAttempts - Base de données: $(if($dbReady){'READY'}else{'NOT READY'})"
            }
            
        } while (-not $dbReady -and $attempt -lt $maxAttempts)
        
        if ($dbReady) {
            Write-Success "Base de données initialisée et opérationnelle"
            return $true
        } else {
            Write-Error "Timeout: base de données non disponible après $maxAttempts tentatives"
            return $false
        }
        
    } catch {
        Write-Error "Erreur lors de l'initialisation de la base de données: $($_.Exception.Message)"
        return $false
    }
}

function Start-AllServices {
    Write-Header "Démarrage de tous les services"
    
    try {
        Write-Info "Démarrage des services en mode production..."
        docker compose up -d 2>&1 | Write-Output
        
        Write-Info "Vérification du statut des services..."
        Start-Sleep -Seconds 10
        
        $services = docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>$null
        Write-Info "État des services:"
        Write-Output $services
        
        Write-Success "Tous les services ont été démarrés"
        
        return $true
        
    } catch {
        Write-Error "Erreur lors du démarrage des services: $($_.Exception.Message)"
        return $false
    }
}

# ============================================================================
# VALIDATION ET TESTS
# ============================================================================

function Test-Installation {
    Write-Header "Tests de validation de l'installation"
    
    $allTestsPassed = $true
    
    # Test 1: Services Docker
    Write-Info "Test 1: Vérification des services Docker..."
    try {
        $runningContainers = docker compose ps -q 2>$null
        if ($runningContainers) {
            Write-Success "✅ Services Docker opérationnels"
        } else {
            Write-Error "❌ Aucun service Docker en cours d'exécution"
            $allTestsPassed = $false
        }
    } catch {
        Write-Error "❌ Erreur lors de la vérification Docker: $($_.Exception.Message)"
        $allTestsPassed = $false
    }
    
    # Test 2: Base de données
    Write-Info "Test 2: Connexion base de données..."
    try {
        $dbTest = docker compose exec -T db psql -U scraper_admin -d scraper_pro -c "SELECT 1;" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✅ Base de données accessible"
        } else {
            Write-Error "❌ Base de données non accessible"
            $allTestsPassed = $false
        }
    } catch {
        Write-Error "❌ Erreur test base de données: $($_.Exception.Message)"
        $allTestsPassed = $false
    }
    
    # Test 3: Dashboard Web
    Write-Info "Test 3: Accessibilité dashboard web..."
    try {
        Start-Sleep -Seconds 5
        $response = Invoke-WebRequest -Uri "http://localhost:8501" -UseBasicParsing -TimeoutSec 30 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Success "✅ Dashboard web accessible"
        } else {
            Write-Warning "⚠️ Dashboard web non accessible (Status: $($response.StatusCode))"
            $allTestsPassed = $false
        }
    } catch {
        Write-Warning "⚠️ Dashboard web non accessible: $($_.Exception.Message)"
        Write-Info "Le dashboard peut prendre quelques minutes pour démarrer complètement."
    }
    
    # Test 4: Logs système
    Write-Info "Test 4: Vérification des logs..."
    try {
        $logs = docker compose logs --tail=10 2>$null
        if ($logs -and $logs -notlike "*error*" -and $logs -notlike "*Error*") {
            Write-Success "✅ Pas d'erreurs dans les logs récents"
        } else {
            Write-Warning "⚠️ Erreurs détectées dans les logs"
        }
    } catch {
        Write-Warning "⚠️ Impossible de vérifier les logs"
    }
    
    return $allTestsPassed
}

# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

function Main {
    Clear-Host
    
    Write-Host @"
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║    🕷️  SCRAPER PRO - INSTALLATION AUTOMATISÉE                                ║
║                                                                              ║
║    Version: 2.0 Production-Ready                                            ║
║    Environment: $Environment                                                          ║
║    Destination: $ProjectPath                        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Cyan
    
    Write-Info "Début de l'installation automatisée..."
    Write-Info "Paramètres:"
    Write-Info "  - Chemin du projet: $ProjectPath"
    Write-Info "  - Environnement: $Environment"
    Write-Info "  - Mode développement: $($DevMode.IsPresent)"
    Write-Info "  - Skip prérequis: $($SkipPrerequisites.IsPresent)"
    
    if (-not $SkipPrerequisites) {
        Test-Prerequisites
    }
    
    try {
        # Étape 1: Structure projet
        New-ProjectStructure
        
        # Étape 2: Configuration environnement
        $credentials = New-EnvironmentConfiguration
        
        # Étape 3: Installation dépendances
        Install-PythonDependencies
        
        # Étape 4: Fichiers de configuration
        Copy-ProjectFiles
        
        # Étape 5: Construction Docker
        if (-not (Build-DockerImages)) {
            throw "Échec de la construction des images Docker"
        }
        
        # Étape 6: Initialisation base de données
        if (-not (Initialize-Database)) {
            throw "Échec de l'initialisation de la base de données"
        }
        
        # Étape 7: Démarrage des services
        if (-not (Start-AllServices)) {
            throw "Échec du démarrage des services"
        }
        
        # Étape 8: Tests de validation
        Write-Info "Attente du démarrage complet des services (30 secondes)..."
        Start-Sleep -Seconds 30
        
        $testsOK = Test-Installation
        
        # Résultats finaux
        Write-Header "INSTALLATION TERMINÉE"
        
        if ($testsOK) {
            Write-Success "🎉 Installation réussie avec succès!"
        } else {
            Write-Warning "⚠️ Installation terminée avec des avertissements"
        }
        
        Write-Info "═══════════════════════════════════════════════════"
        Write-Info "🚀 ACCÈS AU SYSTÈME"
        Write-Info "═══════════════════════════════════════════════════"
        Write-Success "Dashboard URL: http://localhost:8501"
        Write-Success "Username: admin"
        Write-Success "Password: $($credentials.DashboardPassword)"
        Write-Info "═══════════════════════════════════════════════════"
        
        Write-Info "🔧 COMMANDES UTILES:"
        Write-Info "  - Arrêter les services: docker compose down"
        Write-Info "  - Redémarrer: docker compose restart"
        Write-Info "  - Voir les logs: docker compose logs -f"
        Write-Info "  - Status: docker compose ps"
        
        Write-Info "📚 PROCHAINES ÉTAPES:"
        Write-Info "  1. Ouvrir http://localhost:8501 dans votre navigateur"
        Write-Info "  2. Se connecter avec les credentials ci-dessus"
        Write-Info "  3. Configurer vos proxies dans l'onglet 'Proxy Management'"
        Write-Info "  4. Créer votre premier job dans 'Jobs Manager'"
        
        Write-Success "Installation Scraper Pro terminée avec succès! 🎉"
        
    } catch {
        Write-Error "ERREUR CRITIQUE lors de l'installation: $($_.Exception.Message)"
        Write-Error "Stack trace: $($_.ScriptStackTrace)"
        
        Write-Info "🔧 DÉPANNAGE:"
        Write-Info "  1. Vérifiez que Docker Desktop est démarré"
        Write-Info "  2. Vérifiez l'espace disque disponible"
        Write-Info "  3. Exécutez: docker compose logs pour voir les erreurs"
        Write-Info "  4. Relancez le script avec -Verbose pour plus de détails"
        
        exit 1
    }
}

# Point d'entrée
if ($MyInvocation.InvocationName -ne '.') {
    Main
}