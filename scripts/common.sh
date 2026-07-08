#!/usr/bin/env bash
# common.sh -- 共享配置与辅助函数（被各 .sh 脚本 source）
#
# 约定：finance-agent 为主项目，ohos / hnp 为同级的兄弟项目。
# 本地默认目录布局（三个项目在同一级 workspace 下）：
#   <workspace>/
#     finance-agent/          (本仓库，脚本位于其 scripts/ 子目录)
#       scripts/              (本文件所在目录：*.sh + win/*.ps1)
#     finance-assistant-ohos/ (OHOS 工程，缺失则自动克隆)
#     finance_agent_hnp/      (HNP 工程，缺失则自动克隆)
#     release/                (本地打包产物目录，即 workspace/release)
#
# 所有路径均可用环境变量覆盖，便于 CI / 不同机器复用。

# ---- 主项目根 = 本文件所在目录的上一级（本文件位于 finance-agent/scripts/）----
export PROJECT_FINANCE_AGENT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ---- 工作区 = 主项目的上一级（可用 WORKSPACE_ROOT 覆盖）----
# 本地默认：兄弟工程与主项目同级。CI 中把 WORKSPACE_ROOT 指向仓库目录内的 _ws/，
# 使兄弟工程落在 $CI_PROJECT_DIR 内，从而可作为 cache/artifact 在 job 之间传递。
_WORKSPACE="$(dirname "$PROJECT_FINANCE_AGENT")"
export WORKSPACE_ROOT="${WORKSPACE_ROOT:-$_WORKSPACE}"

# ---- 兄弟项目路径（可用环境变量覆盖）----
export PROJECT_OHOS="${PROJECT_OHOS:-$WORKSPACE_ROOT/finance-assistant-ohos}"
export PROJECT_HNP="${PROJECT_HNP:-$WORKSPACE_ROOT/finance_agent_hnp}"

# ---- 产物目录（本地默认 workspace/release；CI 中覆盖为仓库内 release/）----
export RELEASE_DIR="${RELEASE_DIR:-$WORKSPACE_ROOT/release}"

# ---- 派生路径 ----
export PYTHON_SRC="$PROJECT_FINANCE_AGENT/apps/python/src"
export ELECTRON_SRC="$PROJECT_FINANCE_AGENT/apps/electron/src"
export RENDERER_DIST="$PROJECT_FINANCE_AGENT/apps/renderer/dist"

export HNP_CONTENT="$PROJECT_HNP/hnp-content"
export HNP_OUTPUT="$PROJECT_FINANCE_AGENT/release/hnp"
export PROJECT_HNP_FILE="$PROJECT_OHOS/hnp/arm64-v8a/finance-agent-backend.hnp"
export WEB_ENGINE_RES="$PROJECT_OHOS/web_engine/src/main/resources/resfile/resources/app"
export RENDERER_RES="$WEB_ENGINE_RES/renderer"

# ---- 仓库地址（克隆用，可用环境变量覆盖）----
export GIT_HNP_URL="${GIT_HNP_URL:-http://192.168.1.172/finance-agent/finance_agent_hnp.git}"
export GIT_OHOS_URL="${GIT_OHOS_URL:-http://192.168.1.172/finance-agent/finance-assistant-ohos.git}"

# =====================================================================
# 辅助函数
# =====================================================================

# 探测 hnpcli 可执行文件（优先级：环境变量 > 常见路径 > PATH）
detect_hnpcli() {
  if [[ -n "${HNPCLI:-}" ]]; then echo "$HNPCLI"; return; fi
  local candidates=(
    "${OHOS_SDK_HOME:-}/sdk/default/openharmony/toolchains/hnpcli"
    "${COMMAND_LINE_TOOLS:-}/sdk/default/openharmony/toolchains/hnpcli"
    "$HOME/DevEco/command-line-tools/sdk/default/openharmony/toolchains/hnpcli"
    "/opt/harmonyos/command-line-tools/sdk/default/openharmony/toolchains/hnpcli"
    "/opt/deveco/command-line-tools/sdk/default/openharmony/toolchains/hnpcli"
  )
  local c
  for c in "${candidates[@]}"; do
    [[ -x "$c" ]] && { echo "$c"; return; }
  done
  command -v hnpcli 2>/dev/null || true
}

# 探测 hvigorw 可执行文件（Linux 上标准的 OHOS 构建入口）
# 注意：不同版本工具包布局不同——有的在 bin/，有的在 hvigor/bin/，有的在 tools/hvigor/bin/。
detect_hvigorw() {
  if [[ -n "${HVIGORW:-}" ]]; then echo "$HVIGORW"; return; fi
  command -v hvigorw 2>/dev/null || true
  local candidates=(
    "${COMMAND_LINE_TOOLS:-}/bin/hvigorw"
    "${COMMAND_LINE_TOOLS:-}/hvigor/bin/hvigorw"
    "${COMMAND_LINE_TOOLS:-}/tools/hvigor/bin/hvigorw"
    "$HOME/DevEco/command-line-tools/bin/hvigorw"
    "/opt/harmonyos/command-line-tools/bin/hvigorw"
    "/opt/deveco/command-line-tools/bin/hvigorw"
  )
  local c
  for c in "${candidates[@]}"; do
    [[ -x "$c" ]] && { echo "$c"; return; }
  done
  [[ -x "$PROJECT_OHOS/hvigorw" ]] && { echo "$PROJECT_OHOS/hvigorw"; return; }
  echo ""
}

# 探测 ohpm 可执行文件（构建前需先 ohpm install 安装鸿蒙依赖）
detect_ohpm() {
  if [[ -n "${OHPM:-}" ]]; then echo "$OHPM"; return; fi
  command -v ohpm 2>/dev/null || true
  local candidates=(
    "${COMMAND_LINE_TOOLS:-}/bin/ohpm"
    "${COMMAND_LINE_TOOLS:-}/ohpm/bin/ohpm"
    "$HOME/DevEco/command-line-tools/bin/ohpm"
    "/opt/harmonyos/command-line-tools/bin/ohpm"
    "/opt/deveco/command-line-tools/bin/ohpm"
  )
  local c
  for c in "${candidates[@]}"; do
    [[ -x "$c" ]] && { echo "$c"; return; }
  done
  echo ""
}

# 目录同步：优先 rsync（保留排除规则），缺失时回退 cp -r（跨平台兼容）。
# 注意：采用"覆盖式"同步，不清空目标目录——HNP 的 site-packages 里还放着手动解压的
# wheel（numpy/Pillow 等），web_engine 的 resources/app 里还放着 renderer 子目录，
# 清空会误删这些不应由本脚本管理的文件。
sync_dir() {
  local src="$1" dst="$2"
  mkdir -p "$dst"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a \
      --exclude='*.pyc' --exclude='*.pyo' --exclude='__pycache__' \
      --exclude='.eggs' --exclude='*.egg-info' \
      --exclude='node_modules' --exclude='.git' \
      "$src/" "$dst/"
    return $?
  fi
  # 回退：cp -r 覆盖复制，再清理排除项（与上面 rsync --exclude 对应）
  cp -rf "$src/." "$dst/" 2>/dev/null || cp -r "$src/." "$dst/"
  # 注意：本机 Git Bash 的 PATH 被 DevEco/OHOS SDK 注入得很长，会让
  # "find -exec rm" 触发 "environment too large for exec()" 而静默失败，
  # 因此改用 find 内置的 -delete（不另起进程，绕过该限制）。-delete 隐含 -depth，
  # 会先删文件再删目录，对 __pycache__ 这类目录可正确清空。
  find "$dst" \( -name '__pycache__' -o -name 'node_modules' -o -name '.git' -o -name '.eggs' \
    -o -name '*.pyc' -o -name '*.pyo' -o -name '*.egg-info' \) -delete 2>/dev/null || true
  return 0
}

# 若项目目录不存在则克隆（CI 中自动注入 job token 完成鉴权）
clone_if_missing() {
  local url="$1" dir="$2" name="$3"
  if [[ -d "$dir" ]]; then
    echo "  [skip] $name 已存在: $dir"
    return 0
  fi
  local clone_url="$url"
  if [[ -n "${CI_JOB_TOKEN:-}" ]]; then
    # 同实例 GitLab 用 job token 免密克隆
    clone_url="${clone_url/http:\/\//http:\/\/gitlab-ci-token:${CI_JOB_TOKEN}@}"
    clone_url="${clone_url/https:\/\//https:\/\/gitlab-ci-token:${CI_JOB_TOKEN}@}"
  fi
  echo "  [clone] $name -> $dir"
  echo "           $url"
  git clone "$clone_url" "$dir"
}
