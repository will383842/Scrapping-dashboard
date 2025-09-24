Param(
  [switch]$VerboseMode
)
Write-Host "== Scraper Pro - Validation ==" -ForegroundColor Cyan
$errors = @()

function Check-File($path) {
  if(Test-Path $path){ Write-Host "OK  `t$path" -ForegroundColor Green }
  else { Write-Host "MISS`t$path" -ForegroundColor Yellow; $script:errors += $path }
}

# Required files
$paths = @(
  "db\init.sql",
  "db\migrations\001_advanced_features.sql",
  "scraper\utils\redis_coordination.py",
  "scraper\utils\cache_manager.py",
  "scraper\utils\proxy_rotation.py",
  "scraper\utils\proxy_failover.py",
  "scraper\utils\proxy_selector.py",
  "scraper\utils\url_normalizer.py",
  "scraper\utils\seen_urls.py",
  "scraper\utils\content_hasher.py",
  "scraper\utils\error_categorizer.py",
  "scraper\utils\circuit_breaker.py",
  "config\proxy_config.json",
  "config\error_rules.json",
  "monitoring\custom_metrics.py",
  "requirements.txt",
  "docker-compose.yml",
  ".env.example",
  "dashboard\app.py",
  "scraper\spiders\single_url.py",
  "orchestration\scheduler.py"
)

foreach($p in $paths){ Check-File $p }

if($errors.Count -gt 0){
  Write-Host "`nErrors:" -ForegroundColor Red
  $errors | ForEach-Object { Write-Host " - $_" -ForegroundColor Red }
  exit 1
} else {
  Write-Host "`nAll checks passed ✅" -ForegroundColor Green
}
