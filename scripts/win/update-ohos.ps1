# update-ohos.ps1 -- Update backend + frontend in OHOS project
# Usage:
#   .\scripts\win\update-ohos.ps1

$ErrorActionPreference = "Stop"

# ---- Step1: update backend (HNP + Electron src) ----
Write-Host "===== Step 1/2: Updating backend =====" -ForegroundColor Magenta
& "$PSScriptRoot\update-backend.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: update-backend.ps1 failed" -ForegroundColor Red
    exit 1
}

# ---- Step2: update frontend (renderer build + sync) ----
Write-Host ""
Write-Host "===== Step 2/2: Updating frontend =====" -ForegroundColor Magenta
& "$PSScriptRoot\update-frontend.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: update-frontend.ps1 failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "===== All done! OHOS project updated. =====" -ForegroundColor Green
