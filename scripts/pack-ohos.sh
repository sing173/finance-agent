#!/usr/bin/env bash
# pack-ohos.sh -- 打包 HarmonyOS APP（.app，前置：OHOS 工程已通过 update-backend/update-frontend 更新）
# 用法:
#   cd finance-agent
#   ./pack-ohos.sh            # 默认 release
#   ./pack-ohos.sh debug      # debug 模式
#
# 构建工具自动探测：优先 devecocli（Win/Mac），否则 hvigorw（Linux 标准 CLI）。
# 打包成功后已签名的 APP 复制到 RELEASE_DIR。
# 签名：hvigorw 依据工程 build-profile.json5 的 signingConfigs（release 配置引用 cert/ 下的
#       发布证书/Profile）自动签名，无需手动调用 hap-sign-tool。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# 优先取命令行参数，其次取环境变量 BUILD_MODE，最后兜底 debug
BUILD_MODE="${1:-${BUILD_MODE:-release}}"   # debug | release
case "$BUILD_MODE" in
  debug|release) ;;
  *) echo "FAIL: 构建模式必须是 debug 或 release，收到: $BUILD_MODE" >&2; exit 1 ;;
esac

# ---- 构建 APP ----
echo "===== 构建 APP ($BUILD_MODE) ====="

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
    echo "  使用 hvigorw assembleApp ($HVIGORW_BIN)"
    # 安装 ohpm 依赖（仅 hvigorw 路径需要）
    if OHPM_BIN="$(detect_ohpm)"; [[ -n "$OHPM_BIN" ]]; then
      echo "    ohpm install ($OHPM_BIN)"
      (cd "$PROJECT_OHOS" && "$OHPM_BIN" install)
    else
      echo "  WARN: 未找到 ohpm，跳过依赖安装（可能导致构建失败）" >&2
    fi
    # assembleApp 用 --mode project；buildMode=release 时 hvigorw 自动用 build-profile.json5 的
    # release signingConfig（发布证书 financeassistant_ohos.cer + Profile financeassistantProfileRelease.p7b）签名
    (cd "$PROJECT_OHOS" && "$HVIGORW_BIN" assembleApp --mode project -p product=default -p buildMode="$BUILD_MODE")
    ;;
  *)
    echo "  FAIL: 未找到构建工具（devecocli 或 hvigorw）。" >&2
    echo "        Windows/Mac 请安装 @deveco/deveco-cli；Linux 请安装 OHOS CommandLineTools。" >&2
    exit 1
    ;;
esac

# ---- 定位并复制 APP 到产物目录 ----
# assembleApp 产物位于工程级 build/outputs/{productName}/（区别于 assembleHap 的模块级输出）
APP_DIR="$PROJECT_OHOS/build/outputs/default"
if [[ ! -d "$APP_DIR" ]]; then
  APP_DIR="$(find "$PROJECT_OHOS" -type d -name default -path '*/outputs/*' 2>/dev/null | head -1)"
fi

if [[ -z "$APP_DIR" || ! -d "$APP_DIR" ]]; then
  echo "  WARN: 未找到 APP 输出目录" >&2
else
  shopt -s nullglob
  APPS=("$APP_DIR"/*.app)
  shopt -u nullglob
  if [[ ${#APPS[@]} -gt 0 ]]; then
    mkdir -p "$RELEASE_DIR"
    # 只保留确定性命名产物 finance-assistant-ohos-<mode>.app，不保留中间的 *-default-*.app
    # 优先取 signed 包（release 模式默认产出 signed，用于云调试/真机）
    DEST_APP=""
    for a in "${APPS[@]}"; do
      if [[ "$(basename "$a")" == *signed* ]]; then DEST_APP="$a"; break; fi
    done
    [[ -z "$DEST_APP" ]] && DEST_APP="${APPS[0]}"
    cp -f "$DEST_APP" "$RELEASE_DIR/finance-assistant-ohos-$BUILD_MODE.app"
    SIZE=$(du -m "$DEST_APP" | cut -f1)
    echo "  APP: $(basename "$DEST_APP") (${SIZE} MB) -> $RELEASE_DIR/finance-assistant-ohos-$BUILD_MODE.app"
    echo "  OK: APP 已复制到 $RELEASE_DIR"
  else
    echo "  WARN: $APP_DIR 下未找到 .app 文件" >&2
  fi
fi

echo ""
echo "===== 构建完成！====="
