#!/bin/bash
# update-hnp.sh — 将后端代码同步到 HNP 目录并重新打包
# 在 WSL 中执行： bash update-hnp.sh
# 前置条件：
#   1. ~/finance_agent_hnp 目录存在
#   2. D:\HarmonyDevelopment\finance_agent_hnp 已通过 Copy-Item 同步
#   3. Windows 上已安装 hnpcli.exe

set -e

HNP_DIR="$HOME/finance_agent_hnp"
SRC_DIR="$HOME/finance-agent/apps/python/src/finance_agent_backend"
WHEELS_DIR="$HOME/ohos_wheels"

echo "[1/3] 复制后端代码到 HNP..."
rm -rf ${HNP_DIR}/lib/python3.13/site-packages/finance_agent_backend
cp -r ${SRC_DIR} ${HNP_DIR}/lib/python3.13/site-packages/

echo "[2/3] 提交到 git..."
cd ${HNP_DIR}
git add -A
git commit -m "update backend code $(date +%Y-%m-%d-%H%M)" || echo "（无变更，跳过 commit）"
git push

echo "[3/3] 请在 Windows PowerShell 中执行以下命令重新打包："
echo ""
echo '  # 同步 WSL → D 盘'
echo '  robocopy "\\wsl$\Ubuntu\home\zungen\finance_agent_hnp" "D:\HarmonyDevelopment\finance_agent_hnp" /E /XO /XN'
echo ''
echo '  # 重新打包'
echo '  & "D:\Development\DevEco Studio\sdk\default\openharmony\toolchains\hnpcli.exe" pack -i "D:\HarmonyDevelopment\finance_agent_hnp" -o "D:\HarmonyDevelopment\output"'
echo ''
echo '  # 复制到项目'
echo '  Copy-Item "D:\HarmonyDevelopment\output\finance-agent-backend.hnp" "D:\WorkSpace\zungen\finance-assistant-ohos\hnp\arm64-v8a\" -Force'
echo ""
echo "完成！"
