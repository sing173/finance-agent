# update-ohos.ps1 -- Update backend + frontend in OHOS project
# Usage:
#   cd D:\WorkSpace\zungen\finance-agent
#   .\update-ohos.ps1

$ErrorActionPreference = "Stop"

$PROJECT_FINANCE_AGENT = "D:\WorkSpace\zungen\finance-agent"

# ---- Step1: update backend (HNP + Electron src) ----
Write-Host "===== Step 1/2: Updating backend =====" -ForegroundColor Magenta
Set-Location $PROJECT_FINANCE_AGENT
& .\update-backend.ps1
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: update-backend.ps1 failed" -ForegroundColor Red
    exit 1
}

# ---- Step2: update frontend (renderer build + sync) ----
Write-Host ""
Write-Host "===== Step 2/2: Updating frontend =====" -ForegroundColor Magenta
Set-Location $PROJECT_FINANCE_AGENT
& .\update-frontend.ps1
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: update-frontend.ps1 failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "===== All done! OHOS project updated. =====" -ForegroundColor Green
