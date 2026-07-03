# update-hnp.ps1 -- Pure HNP repack script
# Packs hnp-content/ directly (no staging needed, .git is outside hnp-content)
# Usage: in PowerShell
#   cd D:\WorkSpace\zungen\finance-agent\apps\python
#   .\update-hnp.ps1

$ErrorActionPreference = "Stop"

# ---- paths ----
$HNP_LOCAL    = "D:\HarmonyDevelopment\finance_agent_hnp"
$HNP_CONTENT  = "$HNP_LOCAL\hnp-content"   # HNP 内容目录（不含 .git）
$HNPCLI       = "D:\Development\DevEco Studio\sdk\default\openharmony\toolchains\hnpcli.exe"
$OUTPUT_DIR   = "D:\HarmonyDevelopment\output"
$PROJECT_HNP = "D:\WorkSpace\zungen\finance-assistant-ohos\hnp\arm64-v8a\finance-agent-backend.hnp"

# ---- 0. pre-check: hnp.json must exist and be valid ----
$HNP_JSON = "$HNP_CONTENT\hnp.json"
if (-not (Test-Path $HNP_JSON)) {
    Write-Host "[PRE-CHECK] FAIL: $HNP_JSON not found!" -ForegroundColor Red
    exit 1
}
try {
    Get-Content $HNP_JSON -Encoding UTF8 | ConvertFrom-Json | Out-Null
    Write-Host "[PRE-CHECK] OK: $HNP_JSON is valid JSON" -ForegroundColor Green
} catch {
    Write-Host "[PRE-CHECK] FAIL: $HNP_JSON is invalid JSON: $_" -ForegroundColor Red
    exit 1
}

# ---- 1. pack directly from hnp-content ----
Write-Host "[1/2] Packing HNP from $HNP_CONTENT ..." -ForegroundColor Cyan
& $HNPCLI pack -i $HNP_CONTENT -o $OUTPUT_DIR
if ($LASTEXITCODE -ne 0) {
    Write-Host "  FAIL: hnpcli.exe failed (exit code $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path "$OUTPUT_DIR\finance-agent-backend.hnp")) {
    Write-Host "  FAIL: .hnp not generated" -ForegroundColor Red
    exit 1
}
$size = (Get-Item "$OUTPUT_DIR\finance-agent-backend.hnp").Length / 1MB
Write-Host "  OK: $OUTPUT_DIR\finance-agent-backend.hnp ($($size.ToString('F1')) MB)"

# ---- 2. copy to project ----
Write-Host "[2/2] Copying to project..." -ForegroundColor Cyan
Copy-Item "$OUTPUT_DIR\finance-agent-backend.hnp" $PROJECT_HNP -Force
Write-Host "  OK: $PROJECT_HNP"

Write-Host ""
Write-Host "Done! ($($size.ToString('F1')) MB) Rebuild & install in DevEco." -ForegroundColor Green
