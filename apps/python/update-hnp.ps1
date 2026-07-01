# update-hnp.ps1 -- One-click HNP repack (Windows side)
# Usage: in PowerShell
#   cd D:\WorkSpace\zungen\finance-agent\apps\python
#   .\update-hnp.ps1
#
# Before first run: put libsqlite3.so.0 into D:\HarmonyDevelopment\sqlite3\libsqlite3.so.0
# (Ask the user to extract it from OHOS device / SDK sysroot)

$ErrorActionPreference = "Stop"

# ---- paths ----
$PYTHON_SRC      = "D:\WorkSpace\zungen\finance-agent\apps\python\src\finance_agent_backend"
$HNP_LOCAL        = "D:\HarmonyDevelopment\finance_agent_hnp"
$HNPCLI          = "D:\Development\DevEco Studio\sdk\default\openharmony\toolchains\hnpcli.exe"
$OUTPUT_DIR       = "D:\HarmonyDevelopment\output"
$PROJECT_HNP_DIR = "D:\WorkSpace\zungen\finance-assistant-ohos\hnp\arm64-v8a"
# Path to libsqlite3.so.0 (user needs to provide this)
$SQLITE3_SRC    = "D:\HarmonyDevelopment\sqlite3\libsqlite3.so.0"

# ---- 1. copy backend code into HNP dir ----
Write-Host "[1/6] Copying backend code into HNP dir..." -ForegroundColor Cyan
$SITE_PACKAGES = "$HNP_LOCAL\lib\python3.13\site-packages\finance_agent_backend"
if (Test-Path $SITE_PACKAGES) { Remove-Item $SITE_PACKAGES -Recurse -Force }
Copy-Item $PYTHON_SRC $SITE_PACKAGES -Recurse -Force
Write-Host "  OK: $PYTHON_SRC -> $SITE_PACKAGES"

# ---- 2. copy libsqlite3.so.0 into HNP lib/ ----
if (Test-Path $SQLITE3_SRC) {
    Write-Host "[2/6] Copying libsqlite3.so.0 into HNP lib/..." -ForegroundColor Cyan
    $HNP_LIB = "$HNP_LOCAL\lib"
    if (-not (Test-Path $HNP_LIB)) { New-Item -ItemType Directory -Path $HNP_LIB -Force | Out-Null }
    Copy-Item $SQLITE3_SRC "$HNP_LIB\libsqlite3.so.0" -Force
    Write-Host "  OK: libsqlite3.so.0 copied to $HNP_LIB"
} else {
    Write-Host "[2/6] WARNING: libsqlite3.so.0 not found at $SQLITE3_SRC" -ForegroundColor Yellow
    Write-Host "  SQLite3 will not work. See hnp-build-guide.md for how to get this file." -ForegroundColor Yellow
}

# ---- 3. sync to WSL (for git commit) ----
Write-Host "[3/6] Syncing to WSL..." -ForegroundColor Cyan
wsl --exec bash -c "rm -rf ~/finance_agent_hnp/lib/python3.13/site-packages/finance_agent_backend && cp -r /mnt/d/HarmonyDevelopment/finance_agent_hnp/lib/python3.13/site-packages/finance_agent_backend ~/finance_agent_hnp/lib/python3.13/site-packages/"
if (Test-Path $SQLITE3_SRC) {
    wsl --exec bash -c "cp /mnt/d/HarmonyDevelopment/sqlite3/libsqlite3.so.0 ~/finance_agent_hnp/lib/"
}
Write-Host "  OK: WSL sync done"

# ---- 4. sync HNP dir back to D: (consistency) ----
Write-Host "[4/6] Syncing HNP dir to D:..." -ForegroundColor Cyan
robocopy "\\wsl$\Ubuntu\home\zungen\finance_agent_hnp" $HNP_LOCAL /E /XO /XN /NFL /NDL
Write-Host "  OK: D: drive sync done"

# ---- 5. repack HNP ----
Write-Host "[5/6] Repacking HNP..." -ForegroundColor Cyan
& $HNPCLI pack -i $HNP_LOCAL -o $OUTPUT_DIR
if (-not (Test-Path "$OUTPUT_DIR\finance-agent-backend.hnp")) {
    Write-Host "  FAIL: .hnp not generated" -ForegroundColor Red
    exit 1
}
Write-Host "  OK: $OUTPUT_DIR\finance-agent-backend.hnp"

# ---- 6. copy to project ----
Write-Host "[6/6] Copying to project..." -ForegroundColor Cyan
if (-not (Test-Path $PROJECT_HNP_DIR)) { New-Item -ItemType Directory -Path $PROJECT_HNP_DIR -Force | Out-Null }
Copy-Item "$OUTPUT_DIR\finance-agent-backend.hnp" $PROJECT_HNP_DIR -Force
Write-Host "  OK: copied to $PROJECT_HNP_DIR\finance-agent-backend.hnp"

Write-Host ""
Write-Host "HNP update complete!" -ForegroundColor Green
Write-Host "  Package: $PROJECT_HNP_DIR\finance-agent-backend.hnp"
Write-Host "  Now rebuild & install in DevEco."
