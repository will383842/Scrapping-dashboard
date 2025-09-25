# start_app.ps1 (ASCII-safe)
# Starts Docker Desktop if needed, waits for the engine, runs docker compose for the target service,
# then opens the dashboard URL.

param(
  [string]$ServiceName = "scraper-pro-dashboard",  # default service name in docker-compose
  [string]$ComposeFile = "docker-compose.yml",
  [int]$TimeoutSec = 180,
  [switch]$Rebuild,
  [string]$OpenUrl = "http://localhost:8501"
)

$ErrorActionPreference = "Stop"

function Test-DockerReady {
  try {
    $null = docker version --format '{{.Server.Version}}' 2>$null
    if ($LASTEXITCODE -eq 0) { return $true } else { return $false }
  } catch {
    return $false
  }
}

function Start-DockerDesktopIfNeeded {
  if (Test-DockerReady) { return }

  Write-Host "Starting Docker Desktop..."
  $dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
  if (Test-Path $dockerDesktop) {
    Start-Process -FilePath $dockerDesktop | Out-Null
  } else {
    throw "Docker Desktop not found at '$dockerDesktop'. Please install it and run again."
  }

  # Also try to start Windows service if present
  try {
    $svc = Get-Service com.docker.service -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -ne "Running") {
      Start-Service com.docker.service
    }
  } catch { }

  $sw = [Diagnostics.Stopwatch]::StartNew()
  while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
    if (Test-DockerReady) { return }
    Start-Sleep -Seconds 2
  }

  throw "Docker engine did not become ready within $TimeoutSec seconds. Open Docker Desktop manually and try again."
}

# 1) Ensure Docker engine is ready
Write-Host "Checking Docker engine..."
Start-DockerDesktopIfNeeded
Write-Host "Docker engine is ready."

# 2) Determine project directory (script folder when launched with -File; otherwise current directory)
if ($PSScriptRoot) {
  $ProjectDir = $PSScriptRoot
} else {
  $ProjectDir = (Get-Location).Path
}
Set-Location -Path $ProjectDir
Write-Host "Project directory: $ProjectDir"

# 3) Check docker compose availability and compose file
try {
  $null = docker compose version 2>$null
} catch {
  throw "The command 'docker compose' is not available. Please update Docker Desktop."
}

if (-not (Test-Path $ComposeFile)) {
  throw "Compose file '$ComposeFile' not found in '$ProjectDir'."
}

Write-Host "Validating compose file..."
docker compose -f $ComposeFile config | Out-Null

# 4) Optional rebuild, then up the target service
if ($Rebuild) {
  Write-Host "Rebuilding service '$ServiceName' with --no-cache..."
  docker compose -f $ComposeFile build --no-cache $ServiceName
  if ($LASTEXITCODE -ne 0) { throw "docker compose build failed for service '$ServiceName'." }
}

Write-Host "Starting service '$ServiceName'..."
docker compose -f $ComposeFile up -d $ServiceName
if ($LASTEXITCODE -ne 0) {
  throw "docker compose up failed for service '$ServiceName'."
}

# 5) Open browser (optional)
if ($OpenUrl -and $OpenUrl.Trim().Length -gt 0) {
  Start-Sleep -Seconds 3
  Write-Host "Opening: $OpenUrl"
  try {
    Start-Process $OpenUrl
  } catch {
    Write-Warning "Could not open browser automatically. Please open: $OpenUrl"
  }
}

Write-Host "Done."
