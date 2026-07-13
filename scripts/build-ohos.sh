#!/usr/bin/env bash
# build-ohos.sh -- 全量更新 OHOS 工程并打包 APP（.app）
# 用法:
#   cd finance-agent
#   ./build-ohos.sh            # 默认 release
#   ./build-ohos.sh debug      # debug 模式
#
# 构建工具统一使用 command-line-tools 的 hvigorw（Windows / Linux 一致）。
# 打包成功后已签名的 APP 复制到 RELEASE_DIR（默认 workspace/release）。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# 优先取命令行参数，其次取环境变量 BUILD_MODE，最后兜底 release
BUILD_MODE="${1:-${BUILD_MODE:-release}}"   # debug | release
case "$BUILD_MODE" in
  debug|release) ;;
  *) echo "FAIL: 构建模式必须是 debug 或 release，收到: $BUILD_MODE" >&2; exit 1 ;;
esac

# ---- Step 1: 全量更新 OHOS 工程 ----
echo "===== Step 1/2: 更新 OHOS 工程 ====="
"$SCRIPT_DIR/update-ohos.sh"

# ---- Step 2: 构建 APP ----
echo ""
echo "===== Step 2/2: 构建 APP ($BUILD_MODE) ====="
"$SCRIPT_DIR/pack-ohos.sh" "$BUILD_MODE"

echo ""
echo "===== 全流程构建完成！产物见 $RELEASE_DIR ====="
