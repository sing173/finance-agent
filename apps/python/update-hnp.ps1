# update-hnp.ps1 — 一键更新 HNP 包（Windows 端）
# 用法：在 PowerShell 中执行
#   cd D:\WorkSpace\zungen\finance-agent\apps\python
#   .\update-hnp.ps1

$ErrorActionPreference = "Stop"

$WSL_SRC    = "\\wsl$\Ubuntu\home\zungen\finance_agent_hnp"
$DST_LOCAL  = "D:\HarmonyDevelopment\finance_agent_hnp"
$HNPCLI     = "D:\Development\DevEco Studio\sdk\default\openharmony\toolchains\hnpcli.exe"
$OUTPUT_DIR  = "D:\HarmonyDevelopment\output"
$PROJECT_HNP = "D:\WorkSpace\zungen\finance-assistant-ohos\hnp\arm64-v8a"

Write-Host "[1/4] 同步 WSL → D 盘..." -ForegroundColor Cyan
robocopy $WSL_SRC $DST_LOCAL /E /XO /XN /NFL /NDL

Write-Host "[2/4] 重新打包 HNP..." -ForegroundColor Cyan
& $HNPCLI pack -i $DST_LOCAL -o $OUTPUT_DIR

if (-not (Test-Path "$OUTPUT_DIR\finance-agent-backend.hnp")) {
    Write-Host "❌ 打包失败：未生成 .hnp 文件" -ForegroundColor Red
    exit 1
}

Write-Host "[3/4] 复制到项目..." -ForegroundColor Cyan
Copy-Item "$OUTPUT_DIR\finance-agent-backend.hnp" $PROJECT_HNP -Force

Write-Host "[4/4] 提交 HNP 更新到 git..." -ForegroundColor Cyan
Set-Location $PROJECT_HNP\..
git add -A
git commit -m "update hnp: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
git push

Write-Host "✅ HNP 更新完成！" -ForegroundColor Green
Write-Host "   包路径：$PROJECT_HNP\finance-agent-backend.hnp"
Write-Host "   现在在 DevEco 中重新 Build & 安装即可。"
