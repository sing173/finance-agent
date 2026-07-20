#!/usr/bin/env bash
# update-backend.sh -- 更新后端（HNP 打包 + Electron 源码同步）
# 用法:
#   cd finance-agent
#   ./update-backend.sh
#
# 依赖: git, python3, rsync, hnpcli（路径见 common.sh）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

echo "PYTHON_SRC     = $PYTHON_SRC"
echo "ELECTRON_DIST  = $ELECTRON_DIST"
echo "PROJECT_HNP    = $PROJECT_HNP"
echo "PROJECT_OHOS   = $PROJECT_OHOS"

# ---- Step 0: 预检查 ----
echo "[0/4] Pre-check..."
HNP_JSON="$HNP_CONTENT/hnp.json"
if [[ ! -f "$HNP_JSON" ]]; then
  echo "  FAIL: $HNP_JSON 不存在！请确认 HNP 工程已就绪。" >&2
  exit 1
fi
echo "  OK: hnp.json 存在 ($HNP_JSON)"

HNPCLI_BIN="$(detect_hnpcli)"
if [[ -z "$HNPCLI_BIN" ]]; then
  echo "  FAIL: 未找到 hnpcli。请设置环境变量 HNPCLI 或安装 OHOS CommandLineTools。" >&2
  exit 1
fi
echo "  hnpcli = $HNPCLI_BIN"

# ---- Step 1: 同步 Python 源码到 HNP site-packages ----
echo "[1/4] 同步 Python 源码到 HNP site-packages..."
SITE_PACKAGES="$HNP_CONTENT/lib/python3.12/site-packages"
mkdir -p "$SITE_PACKAGES"
sync_dir "$PYTHON_SRC" "$SITE_PACKAGES"
echo "  OK"

# ---- Step 2: 打包 HNP ----
echo "[2/4] 打包 HNP..."
mkdir -p "$HNP_OUTPUT"
"$HNPCLI_BIN" pack -i "$HNP_CONTENT" -o "$HNP_OUTPUT"
HNP_FILE="$HNP_OUTPUT/finance-agent-backend.hnp"
if [[ ! -f "$HNP_FILE" ]]; then
  echo "  FAIL: 未生成 .hnp 文件" >&2
  exit 1
fi
SIZE=$(du -m "$HNP_FILE" | cut -f1)
echo "  OK: $HNP_FILE (${SIZE} MB)"

# ---- Step 3: 复制 HNP 到 OHOS 工程 ----
echo "[3/4] 复制 HNP 到 OHOS 工程..."
mkdir -p "$(dirname "$PROJECT_HNP_FILE")"
cp -f "$HNP_FILE" "$PROJECT_HNP_FILE"
echo "  OK: $PROJECT_HNP_FILE"

# ---- Step 4: 编译 Electron TS -> JS 并同步到 web_engine ----
echo "[4/4] 编译 Electron TS -> JS 并同步到 web_engine..."
( cd "$PROJECT_FINANCE_AGENT/apps/electron" && "$TSPC" -p tsconfig.json ) || { echo "  FAIL: Electron TS 编译失败" >&2; exit 1; }
sync_dir "$ELECTRON_DIST" "$WEB_ENGINE_RES"
echo "  OK"

echo ""
echo "Done! 后端已更新。"
