#!/usr/bin/env bash
# pack-ohos.sh -- 打包 HarmonyOS（按 flavor 区分产物与签名）
# 用法:
#   cd finance-agent
#   ./pack-ohos.sh prod             # 正式 app：assembleApp -p product=prod   -> 仅保留 .app
#   ./pack-ohos.sh test [buildMode] # 测试 app：assembleApp -p product=default -> 保留 .app + .hap
#   ./pack-ohos.sh debug [buildMode]# 调试 hap：assembleHap  -p product=default -> 仅保留 .hap
#   buildMode: debug | release（可选；默认 prod/test=release，debug=debug）
#
# 构建工具统一使用 command-line-tools 的 hvigorw（Windows / Linux 一致）。
# 签名由 build-profile.json5 的 product 决定：prod -> release 签名，default -> debug 签名。
# 产物复制到 RELEASE_DIR（默认 workspace/release），按 flavor 命名。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# ---- 参数解析 ----
FLAVOR="${1:-prod}"          # prod | test | debug
BUILD_MODE="${2:-}"
case "$FLAVOR" in
  prod|test|debug) ;;
  *) echo "FAIL: flavor 必须是 prod / test / debug，收到: $FLAVOR" >&2; exit 1 ;;
esac
# flavor 默认 buildMode
if [[ -z "$BUILD_MODE" ]]; then
  case "$FLAVOR" in
    prod)  BUILD_MODE=release ;;
    test)  BUILD_MODE=release ;;
    debug) BUILD_MODE=debug ;;
  esac
fi
case "$BUILD_MODE" in
  debug|release) ;;
  *) echo "FAIL: buildMode 必须是 debug 或 release，收到: $BUILD_MODE" >&2; exit 1 ;;
esac

# 产出 hap 的模块（模块级 assembleHap 需要 -p module=<模块名>@<target>），可用环境变量覆盖
HAP_MODULE="${OHOS_HAP_MODULE:-electron@default}"

# flavor -> product / hvigor 任务 / 构建模式 / 保留产物
# 注意：assembleApp 是「项目级」任务（--mode project）；assembleHap 是「模块级」任务
#       （--mode module -p module=...），两者的 mode 不能混用，否则报 "Task not found"。
case "$FLAVOR" in
  prod)  PRODUCT=prod;    HVIGOR_TASK=assembleApp; HVIGOR_MODE=project; KEEP_APP=1; KEEP_HAP=0 ;;
  test)  PRODUCT=default; HVIGOR_TASK=assembleApp; HVIGOR_MODE=project; KEEP_APP=1; KEEP_HAP=1 ;;
  debug) PRODUCT=default; HVIGOR_TASK=assembleHap; HVIGOR_MODE=module;  KEEP_APP=0; KEEP_HAP=1 ;;
esac

# ---- 定位 hvigorw ----
HVIGORW_BIN="$(detect_hvigorw)"
if [[ -z "$HVIGORW_BIN" ]]; then
  echo "  FAIL: 未找到 hvigorw（command-line-tools）。" >&2
  echo "        请安装 OHOS Command Line Tools 并配置 COMMAND_LINE_TOOLS 环境变量，" >&2
  echo "        或在 PATH 中提供 hvigorw / hvigorw.bat。" >&2
  exit 1
fi
echo "  使用 hvigorw ($HVIGORW_BIN)"
echo "  flavor=$FLAVOR product=$PRODUCT task=$HVIGOR_TASK mode=$HVIGOR_MODE buildMode=$BUILD_MODE"

# 安装 ohpm 依赖（hvigorw 构建前需要）
if OHPM_BIN="$(detect_ohpm)"; [[ -n "$OHPM_BIN" ]]; then
  echo "    ohpm install ($OHPM_BIN)"
  run_in_ohos "$OHPM_BIN" install
else
  echo "  WARN: 未找到 ohpm，跳过依赖安装（可能导致构建失败）" >&2
fi

# ---- 构建 ----
# 项目级（assembleApp）与模块级（assembleHap）参数不同：
#   - 项目级：--mode project
#   - 模块级：--mode module -p module=<模块>@<target>
if [[ "$HVIGOR_MODE" == "module" ]]; then
  run_in_ohos "$HVIGORW_BIN" "$HVIGOR_TASK" --mode module -p "module=$HAP_MODULE" -p "product=$PRODUCT" -p "buildMode=$BUILD_MODE"
else
  run_in_ohos "$HVIGORW_BIN" "$HVIGOR_TASK" --mode project -p "product=$PRODUCT" -p "buildMode=$BUILD_MODE"
fi

# ---- 收集产物 ----
# 项目级 .app 输出：build/outputs/{product}/
APP_OUT="$PROJECT_OHOS/build/outputs/$PRODUCT"
# 模块级 .hap 输出：electron/build/{product}/outputs/default/（product 不存在时回退 default）
HAP_OUT="$PROJECT_OHOS/electron/build/$PRODUCT/outputs/default"
[[ -d "$HAP_OUT" ]] || HAP_OUT="$PROJECT_OHOS/electron/build/default/outputs/default"

mkdir -p "$RELEASE_DIR"
shopt -s nullglob
if [[ "$KEEP_APP" -eq 1 ]]; then
  APPS=("$APP_OUT"/*.app)
  if [[ ${#APPS[@]} -gt 0 ]]; then
    DEST=""
    for a in "${APPS[@]}"; do
      [[ "$(basename "$a")" == *signed* ]] && DEST="$a"
    done
    [[ -z "$DEST" ]] && DEST="${APPS[0]}"
    cp -f "$DEST" "$RELEASE_DIR/finance-assistant-ohos-$FLAVOR.app"
    SIZE=$(du -m "$DEST" | cut -f1)
    echo "  APP: $(basename "$DEST") (${SIZE} MB) -> $RELEASE_DIR/finance-assistant-ohos-$FLAVOR.app"
  else
    echo "  WARN: 未找到 .app（$APP_OUT）" >&2
  fi
fi
if [[ "$KEEP_HAP" -eq 1 ]]; then
  HAPS=("$HAP_OUT"/*.hap)
  if [[ ${#HAPS[@]} -gt 0 ]]; then
    # 优先取已签名的 *-signed.hap；没有则退回第一个（排除 *-unsigned.hap）
    HDEST=""
    for h in "${HAPS[@]}"; do
      [[ "$(basename "$h")" == *signed* && "$(basename "$h")" != *unsigned* ]] && HDEST="$h"
    done
    if [[ -z "$HDEST" ]]; then
      for h in "${HAPS[@]}"; do
        [[ "$(basename "$h")" != *unsigned* ]] && { HDEST="$h"; break; }
      done
    fi
    [[ -z "$HDEST" ]] && HDEST="${HAPS[0]}"
    cp -f "$HDEST" "$RELEASE_DIR/finance-assistant-ohos-$FLAVOR.hap"
    SIZE=$(du -m "$HDEST" | cut -f1)
    echo "  HAP: $(basename "$HDEST") (${SIZE} MB) -> $RELEASE_DIR/finance-assistant-ohos-$FLAVOR.hap"
  else
    echo "  WARN: 未找到 .hap（$HAP_OUT）" >&2
  fi
fi
shopt -u nullglob

echo ""
echo "===== 构建完成！($FLAVOR) ====="
