#!/usr/bin/env bash
# build-ohos.sh -- 全量更新 OHOS 工程并打包（按 flavor 区分产物）
# 用法:
#   cd finance-agent
#   ./build-ohos.sh            # 默认 prod（正式 app）
#   ./build-ohos.sh test       # 测试 app（+ hap）
#   ./build-ohos.sh debug      # 调试 hap
#   ./build-ohos.sh prod debug # prod + 指定 buildMode（一般不这样用）
#
# 构建工具统一使用 command-line-tools 的 hvigorw（Windows / Linux 一致）。
# 打包成功后产物复制到 RELEASE_DIR（默认 workspace/release）。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

FLAVOR="${1:-prod}"            # prod | test | debug
BUILD_MODE="${2:-}"            # debug | release（可选，按 flavor 取默认）

# ---- Step 1: 全量更新 OHOS 工程 ----
echo "===== Step 1/2: 更新 OHOS 工程 ====="
"$SCRIPT_DIR/update-ohos.sh"

# ---- Step 2: 构建 ----
echo ""
echo "===== Step 2/2: 构建 ($FLAVOR) ====="
if [[ -n "$BUILD_MODE" ]]; then
  "$SCRIPT_DIR/pack-ohos.sh" "$FLAVOR" "$BUILD_MODE"
else
  "$SCRIPT_DIR/pack-ohos.sh" "$FLAVOR"
fi

echo ""
echo "===== 全流程构建完成！产物见 $RELEASE_DIR ====="
