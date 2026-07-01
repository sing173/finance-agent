# update-hnp.ps1 -- One-click HNP repack (Windows side)
# Usage: in PowerShell
#   cd D:\WorkSpace\zungen\finance-agent\apps\python
#   .\update-hnp.ps1

$ErrorActionPreference = "Stop"

# ---- paths ----
$PYTHON_SRC      = "D:\WorkSpace\zungen\finance-agent\apps\python\src\finance_agent_backend"
$HNP_LOCAL        = "D:\HarmonyDevelopment\finance_agent_hnp"
$HNPCLI          = "D:\Development\DevEco Studio\sdk\default\openharmony\toolchains\hnpcli.exe"
$OUTPUT_DIR       = "D:\HarmonyDevelopment\output"
$PROJECT_HNP_DIR = "D:\WorkSpace\zungen\finance-assistant-ohos\hnp\arm64-v8a"

# ---- 1. copy backend code into HNP dir ----
Write-Host "[1/5] Copying backend code into HNP dir..." -ForegroundColor Cyan
$SITE_PACKAGES = "$HNP_LOCAL\lib\python3.13\site-packages\finance_agent_backend"
if (Test-Path $SITE_PACKAGES) { Remove-Item $SITE_PACKAGES -Recurse -Force }
Copy-Item $PYTHON_SRC $SITE_PACKAGES -Recurse -Force
Write-Host "  OK: $PYTHON_SRC -> $SITE_PACKAGES"

# ---- 2. sync to WSL (for git commit) ----
Write-Host "[2/5] Syncing to WSL..." -ForegroundColor Cyan
wsl --exec bash -c "rm -rf ~/finance_agent_hnp/lib/python3.13/site-packages/finance_agent_backend && cp -r /mnt/d/HarmonyDevelopment/finance_agent_hnp/lib/python3.13/site-packages/finance_agent_backend ~/finance_agent_hnp/lib/python3.13/site-packages/"
Write-Host "  OK: WSL sync done"

# ---- 3. sync HNP dir back to D: (consistency) ----
Write-Host "[3/5] Syncing HNP dir to D:..." -ForegroundColor Cyan
robocopy "\\wsl$\Ubuntu\home\zungen\finance_agent_hnp" $HNP_LOCAL /E /XO /XN /NFL /NDL
Write-Host "  OK: D: drive sync done"

# ---- 4. repack HNP ----
Write-Host "[4/5] Repacking HNP..." -ForegroundColor Cyan
& $HNPCLI pack -i $HNP_LOCAL -o $OUTPUT_DIR
if (-not (Test-Path "$OUTPUT_DIR\finance-agent-backend.hnp")) {
    Write-Host "  FAIL: .hnp not generated" -ForegroundColor Red
    exit 1
}
Write-Host "  OK: $OUTPUT_DIR\finance-agent-backend.hnp"

# ---- 5. copy to project ----
Write-Host "[5/5] Copying to project..." -ForegroundColor Cyan
if (-not (Test-Path $PROJECT_HNP_DIR)) { New-Item -ItemType Directory -Path $PROJECT_HNP_DIR -Force | Out-Null }
Copy-Item "$OUTPUT_DIR\finance-agent-backend.hnp" $PROJECT_HNP_DIR -Force
Write-Host "  OK: copied to $PROJECT_HNP_DIR\finance-agent-backend.hnp"

Write-Host ""
Write-Host "HNP update complete!" -ForegroundColor Green
Write-Host "  Package: $PROJECT_HNP_DIR\finance-agent-backend.hnp"
Write-Host "  Now rebuild & install in DevEco."
