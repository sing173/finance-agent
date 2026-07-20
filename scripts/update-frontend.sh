#!/usr/bin/env bash
# update-frontend.sh -- 构建 renderer 并同步到 OHOS 工程
# 用法:
#   cd finance-agent
#   ./update-frontend.sh
#
# 依赖: node/npm

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# ---- Step 0: 预检查 ----
echo "[0/2] Pre-check..."
[[ -d "$PROJECT_FINANCE_AGENT" ]] || { echo "  FAIL: finance-agent 不存在" >&2; exit 1; }
[[ -d "$PROJECT_OHOS" ]] || { echo "  FAIL: finance-assistant-ohos 不存在（先运行 update-ohos.sh 自动克隆）" >&2; exit 1; }

# 首次构建确保依赖已安装（幂等：node_modules 存在则跳过）
if [[ ! -d "$PROJECT_FINANCE_AGENT/node_modules" ]]; then
  echo "  [npm] 安装依赖..."
  (cd "$PROJECT_FINANCE_AGENT" && npm install)
fi

# ---- Step 1: 构建 renderer ----
echo "[1/2] 构建 renderer..."
(cd "$PROJECT_FINANCE_AGENT" && npm run build -w apps/renderer)
if [[ ! -d "$RENDERER_DIST" ]]; then
  echo "  FAIL: 构建后未找到 dist/ : $RENDERER_DIST" >&2
  exit 1
fi
echo "  OK: dist/ 已生成"

# ---- Step 2: 同步 dist/ 到 web_engine ----
echo "[2/2] 同步 dist/ 到 web_engine..."
mkdir -p "$RENDERER_RES"
sync_dir "$RENDERER_DIST" "$RENDERER_RES"
COUNT=$(find "$RENDERER_RES" -type f | wc -l)
echo "  OK: $COUNT 个文件已同步到 $RENDERER_RES"

echo ""
echo "Done! 前端已更新。"
