#!/usr/bin/env bash
# update-ohos.sh -- 更新 OHOS 工程（后端 + 前端）
# 用法:
#   cd finance-agent
#   ./update-ohos.sh
#
# 会自动检查并克隆缺失的兄弟工程（finance_agent_hnp / finance-assistant-ohos）。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# ---- 确保兄弟工程存在 ----
echo "===== 检查兄弟工程 ====="
clone_if_missing "$GIT_HNP_URL"  "$PROJECT_HNP"  "finance_agent_hnp"
clone_if_missing "$GIT_OHOS_URL" "$PROJECT_OHOS" "finance-assistant-ohos"

# ---- Step 1: 更新后端（HNP + Electron 源码）----
echo ""
echo "===== Step 1/2: 更新后端 ====="
"$SCRIPT_DIR/update-backend.sh"

# ---- Step 2: 更新前端（renderer 构建 + 同步）----
echo ""
echo "===== Step 2/2: 更新前端 ====="
"$SCRIPT_DIR/update-frontend.sh"

echo ""
echo "===== 全部完成！OHOS 工程已更新。 ====="
