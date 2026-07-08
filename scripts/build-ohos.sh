#!/usr/bin/env bash
# build-ohos.sh -- 全量更新 OHOS 工程并打包 HAP
# 用法:
#   cd finance-agent
#   ./build-ohos.sh            # 默认 debug
#   ./build-ohos.sh release    # release 模式
#
# 构建工具自动探测：优先 devecocli（Win/Mac），否则 hvigorw（Linux 标准 CLI）。
# 打包成功后 HAP 复制到 RELEASE_DIR（默认 workspace/release）。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

BUILD_MODE="${1:-debug}"   # debug | release
case "$BUILD_MODE" in
  debug|release) ;;
  *) echo "FAIL: 构建模式必须是 debug 或 release，收到: $BUILD_MODE" >&2; exit 1 ;;
esac

# ---- Step 1: 全量更新 OHOS 工程 ----
echo "===== Step 1/2: 更新 OHOS 工程 ====="
"$SCRIPT_DIR/update-ohos.sh"

# ---- Step 2: 构建 HAP ----
echo ""
echo "===== Step 2/2: 构建 HAP ($BUILD_MODE) ====="

BUILD_TOOL=""
if command -v devecocli >/dev/null 2>&1; then
  BUILD_TOOL="devecocli"
elif HVIGORW_BIN="$(detect_hvigorw)"; [[ -n "$HVIGORW_BIN" ]]; then
  BUILD_TOOL="hvigorw"
fi

case "$BUILD_TOOL" in
  devecocli)
    echo "  使用 devecocli build"
    (cd "$PROJECT_OHOS" && devecocli build --build-mode "$BUILD_MODE")
    ;;
  hvigorw)
    echo "  使用 hvigorw assembleHap ($HVIGORW_BIN)"
    # 安装 ohpm 依赖（仅 hvigorw 路径需要）
    if OHPM_BIN="$(detect_ohpm)"; [[ -n "$OHPM_BIN" ]]; then
      echo "    ohpm install ($OHPM_BIN)"
      (cd "$PROJECT_OHOS" && "$OHPM_BIN" install)
    else
      echo "  WARN: 未找到 ohpm，跳过依赖安装（可能导致构建失败）" >&2
    fi
    (cd "$PROJECT_OHOS" && "$HVIGORW_BIN" assembleHap --mode module -p product=default -p buildMode="$BUILD_MODE")
    ;;
  *)
    echo "  FAIL: 未找到构建工具（devecocli 或 hvigorw）。" >&2
    echo "        Windows/Mac 请安装 @deveco/deveco-cli；Linux 请安装 OHOS CommandLineTools。" >&2
    exit 1
    ;;
esac

# ---- 定位并复制 HAP 到产物目录 ----
HAP_DIR="$PROJECT_OHOS/electron/build/default/outputs/default"
if [[ ! -d "$HAP_DIR" ]]; then
  HAP_DIR="$(find "$PROJECT_OHOS" -type d -name default -path '*/outputs/*' 2>/dev/null | head -1)"
fi

if [[ -z "$HAP_DIR" || ! -d "$HAP_DIR" ]]; then
  echo "  WARN: 未找到 HAP 输出目录" >&2
else
  shopt -s nullglob
  HAPS=("$HAP_DIR"/*.hap)
  shopt -u nullglob
  if [[ ${#HAPS[@]} -gt 0 ]]; then
    mkdir -p "$RELEASE_DIR"
    FIRST=1
    for h in "${HAPS[@]}"; do
      cp -f "$h" "$RELEASE_DIR/$(basename "$h")"
      SIZE=$(du -m "$h" | cut -f1)
      echo "  HAP: $(basename "$h") (${SIZE} MB) -> $RELEASE_DIR/"
      # 复制首个为确定性名称（带构建模式），便于 CI release 链接
      if [[ $FIRST -eq 1 ]]; then
        cp -f "$h" "$RELEASE_DIR/finance-assistant-ohos-$BUILD_MODE.hap"
        FIRST=0
      fi
    done
    echo "  OK: HAP 已复制到 $RELEASE_DIR"
  else
    echo "  WARN: $HAP_DIR 下未找到 .hap 文件" >&2
  fi
fi

echo ""
echo "===== 构建完成！====="
