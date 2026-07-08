# update-backend.ps1 -- Update backend (HNP pack + Electron src sync)
# Usage:
#   cd D:\WorkSpace\zungen\finance-agent\apps\python
#   .\update-backend.ps1

$ErrorActionPreference = "Stop"

# ---- Project roots (edit these if needed) ----
$PROJECT_FINANCE_AGENT = "D:\WorkSpace\zungen\finance-agent"
$PROJECT_OHOS          = "D:\WorkSpace\zungen\finance-assistant-ohos"
$HNP_LOCAL             = "D:\HarmonyDevelopment\finance_agent_hnp"
$HNPCLI                = "D:\Development\DevEco Studio\sdk\default\openharmony\toolchains\hnpcli.exe"

# ---- Derived paths ----
$PYTHON_SRC     = "$PROJECT_FINANCE_AGENT\apps\python\src"
$ELECTRON_SRC   = "$PROJECT_FINANCE_AGENT\apps\electron\src"
$HNP_CONTENT    = "$HNP_LOCAL\hnp-content"
$HNP_OUTPUT     = "$PROJECT_FINANCE_AGENT\release\hnp"
$PROJECT_HNP    = "$PROJECT_OHOS\hnp\arm64-v8a\finance-agent-backend.hnp"
$WEB_ENGINE_RES = "$PROJECT_OHOS\web_engine\src\main\resources\resfile\resources\app"

Write-Host "PYTHON_SRC = $PYTHON_SRC" -ForegroundColor Yellow
Write-Host "ELECTRON_SRC = $ELECTRON_SRC" -ForegroundColor Yellow

# ---- Step 0: pre-check ----
Write-Host "[0/4] Pre-check..." -ForegroundColor Cyan
$HNP_JSON = "$HNP_CONTENT\hnp.json"
if (-not (Test-Path $HNP_JSON)) {
    Write-Host "  FAIL: $HNP_JSON not found!" -ForegroundColor Red
    exit 1
}
try {
    Get-Content $HNP_JSON -Encoding UTF8 | ConvertFrom-Json | Out-Null
    Write-Host "  OK: hnp.json is valid" -ForegroundColor Green
} catch {
    Write-Host "  FAIL: hnp.json invalid: $_" -ForegroundColor Red
    exit 1
}

# ---- Step 1: sync Python src to HNP site-packages ----
Write-Host "[1/4] Syncing Python src to HNP site-packages..." -ForegroundColor Cyan
$SITE_PACKAGES = "$HNP_CONTENT\lib\python3.12\site-packages"
robocopy.exe "$PYTHON_SRC" "$SITE_PACKAGES" /E /XF *.pyc *.pyo /XD __pycache__ .eggs *.egg-info /NFL /NDL /NJH /NJS
if ($LASTEXITCODE -gt 7) { Write-Host "  FAIL: robocopy Python src failed" -ForegroundColor Red; exit 1 }
Write-Host "  OK" -ForegroundColor Green

# ---- Step 2: pack HNP ----
Write-Host "[2/4] Packing HNP..." -ForegroundColor Cyan
New-Item -ItemType Directory -Path $HNP_OUTPUT -Force | Out-Null
& $HNPCLI pack -i $HNP_CONTENT -o $HNP_OUTPUT
if ($LASTEXITCODE -ne 0) {
    Write-Host "  FAIL: hnpcli.exe failed (exit code $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}
$HNP_FILE = "$HNP_OUTPUT\finance-agent-backend.hnp"
if (-not (Test-Path $HNP_FILE)) {
    Write-Host "  FAIL: .hnp not generated" -ForegroundColor Red
    exit 1
}
$size = (Get-Item $HNP_FILE).Length / 1MB
Write-Host "  OK: $HNP_FILE ($($size.ToString('F1')) MB)" -ForegroundColor Green

# ---- Step 3: copy HNP to project ----
Write-Host "[3/4] Copying HNP to project..." -ForegroundColor Cyan
Copy-Item $HNP_FILE $PROJECT_HNP -Force
Write-Host "  OK: $PROJECT_HNP" -ForegroundColor Green

# ---- Step 4: sync Electron src to web_engine ----
Write-Host "[4/4] Syncing Electron src to web_engine..." -ForegroundColor Cyan
robocopy.exe "$ELECTRON_SRC" "$WEB_ENGINE_RES" /E /XD node_modules .git /NFL /NDL /NJH /NJS
if ($LASTEXITCODE -gt 7) { Write-Host "  FAIL: robocopy Electron src failed" -ForegroundColor Red; exit 1 }
Write-Host "  OK" -ForegroundColor Green

Write-Host ""
Write-Host "Done! Rebuild & install in DevEco." -ForegroundColor Green
exit 0
