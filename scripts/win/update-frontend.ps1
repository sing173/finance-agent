# update-frontend.ps1 -- Build renderer and sync to OHOS project
# Usage:
#   cd D:\WorkSpace\zungen\finance-agent
#   .\update-frontend.ps1

$ErrorActionPreference = "Stop"

# ---- Project roots ----
$PROJECT_FINANCE_AGENT = "D:\WorkSpace\zungen\finance-agent"
$PROJECT_OHOS          = "D:\WorkSpace\zungen\finance-assistant-ohos"

# ---- Derived paths ----
$RENDERER_DIST = "$PROJECT_FINANCE_AGENT\apps\renderer\dist"
$WEB_ENGINE_RES = "$PROJECT_OHOS\web_engine\src\main\resources\resfile\resources\app\renderer"

# ---- Step 0: pre-check ----
Write-Host "[0/2] Pre-check..." -ForegroundColor Cyan
if (-not (Test-Path $PROJECT_FINANCE_AGENT)) {
    Write-Host "  FAIL: finance-agent project not found: $PROJECT_FINANCE_AGENT" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $PROJECT_OHOS)) {
    Write-Host "  FAIL: finance-assistant-ohos project not found: $PROJECT_OHOS" -ForegroundColor Red
    exit 1
}
Write-Host "  OK" -ForegroundColor Green

# ---- Step 1: build renderer ----
Write-Host "[1/2] Building renderer..." -ForegroundColor Cyan
Set-Location $PROJECT_FINANCE_AGENT
& npm run build -w apps/renderer
if ($LASTEXITCODE -ne 0) {
    Write-Host "  FAIL: renderer build failed (exit code $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $RENDERER_DIST)) {
    Write-Host "  FAIL: dist/ not found after build: $RENDERER_DIST" -ForegroundColor Red
    exit 1
}
Write-Host "  OK: dist/ generated" -ForegroundColor Green

# ---- Step 2: sync dist/ to web_engine ----
Write-Host "[2/2] Syncing dist/ to web_engine..." -ForegroundColor Cyan
New-Item -ItemType Directory -Path $WEB_ENGINE_RES -Force | Out-Null
robocopy.exe $RENDERER_DIST $WEB_ENGINE_RES /E /NFL /NDL /NJH /NJS
if ($LASTEXITCODE -gt 7) {
    Write-Host "  FAIL: robocopy dist/ failed" -ForegroundColor Red
    exit 1
}
$fileCount = (Get-ChildItem $WEB_ENGINE_RES -Recurse -File).Count
Write-Host "  OK: $fileCount files synced to $WEB_ENGINE_RES" -ForegroundColor Green

Write-Host ""
Write-Host "Done! Frontend updated." -ForegroundColor Green
exit 0
