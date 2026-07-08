# build-ohos.ps1 -- Update OHOS project and build HAP via deveco-cli
# Usage:
#   .\scripts\win\build-ohos.ps1                 # debug build (default)
#   .\scripts\win\build-ohos.ps1 -BuildMode release   # release build

param(
    [string]$BuildMode = "debug"   # debug | release
)

$ErrorActionPreference = "Stop"

$PROJECT_FINANCE_AGENT = "D:\WorkSpace\zungen\finance-agent"
$PROJECT_OHOS         = "D:\WorkSpace\zungen\finance-assistant-ohos"

# Validate BuildMode
if ($BuildMode -ne "debug" -and $BuildMode -ne "release") {
    Write-Host "FAIL: -BuildMode must be 'debug' or 'release'" -ForegroundColor Red
    exit 1
}

# ---- Step1: update ohos project ----
Write-Host "===== Step 1/2: Updating OHOS project =====" -ForegroundColor Magenta
& "$PSScriptRoot\update-ohos.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: update-ohos.ps1 failed" -ForegroundColor Red
    exit 1
}

# ---- Step2: build HAP via deveco-cli ----
Write-Host ""
Write-Host "===== Step 2/2: Building HAP ($BuildMode) =====" -ForegroundColor Magenta
Set-Location $PROJECT_OHOS

# Check devecocli is available
$devecoCli = Get-Command devecocli -ErrorAction SilentlyContinue
if (-not $devecoCli) {
    Write-Host "  WARN: devecocli not found in PATH, trying npm global bin..." -ForegroundColor Yellow
    # Try to find devecocli in npm global bin
    $npmGlobalBin = & npm bin -g 2>$null
    $devecoCliPath = Join-Path $npmGlobalBin "devecocli.cmd"
    if (Test-Path $devecoCliPath) {
        $devecoCli = $devecoCliPath
    } else {
        Write-Host "  FAIL: devecocli not found. Install with: npm install -g @deveco/deveco-cli@latest" -ForegroundColor Red
        exit 1
    }
}

& devecocli build --build-mode $BuildMode
if ($LASTEXITCODE -ne 0) {
    Write-Host "  FAIL: devecocli build failed (exit code $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "===== Build complete! =====" -ForegroundColor Green

# devecocli build outputs to <module>/build/default/outputs/default/
# The electron module's HAP is under electron/build/
$hapDir = "$PROJECT_OHOS\electron\build\default\outputs\default"
if (Test-Path $hapDir) {
    $hapFiles = Get-ChildItem $hapDir -Filter "*.hap"
    if ($hapFiles.Count -gt 0) {
        Write-Host ""
        Write-Host "  HAP output:" -ForegroundColor Cyan
        foreach ($f in $hapFiles) {
            $sizeMB = [math]::Round($f.Length / 1MB, 1)
            Write-Host "    $($f.FullName)  ($sizeMB MB)" -ForegroundColor Green
        }
    } else {
        Write-Host "  WARN: no .hap found in $hapDir" -ForegroundColor Yellow
    }
} else {
    Write-Host "  WARN: output dir not found: $hapDir" -ForegroundColor Yellow
}
