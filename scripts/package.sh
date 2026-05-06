#!/bin/bash
set -e

# Finance Assistant 一键打包脚本
# 用法: ./scripts/package.sh [platform]
# platform: win | mac | linux (默认: 当前系统)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PLATFORM="${1:-auto}"

echo "=========================================="
echo "  Finance Assistant 打包脚本"
echo "=========================================="
echo "项目目录: $PROJECT_ROOT"
echo "目标平台: $PLATFORM"
echo ""

# 进入项目根目录
cd "$PROJECT_ROOT"

# 检测当前系统
detect_platform() {
  case "$(uname -s)" in
    Linux*)  echo "linux";;
    Darwin*) echo "mac";;
    MINGW*|MSYS*|CYGWIN*) echo "win";;
    *)       echo "unknown";;
  esac
}

# 如果指定 auto，则自动检测
if [ "$PLATFORM" = "auto" ]; then
  PLATFORM=$(detect_platform)
  echo "自动检测到平台: $PLATFORM"
fi

# 检查依赖
check_dependencies() {
  echo "[1/5] 检查依赖..."

  if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安装，请先安装 Node.js >= 18"
    exit 1
  fi

  if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装，请先安装 Python >= 3.11"
    exit 1
  fi

  echo "✅ Node.js: $(node --version)"
  echo "✅ Python: $(python3 --version)"
}

# 安装 npm 依赖
install_npm_deps() {
  echo ""
  echo "[2/5] 安装 npm 依赖..."
  npm install
  echo "✅ npm 依赖安装完成"
}

# 打包 Python 后端
package_python() {
  echo ""
  echo "[3/5] 打包 Python 后端..."

  cd "$PROJECT_ROOT/apps/python"

  # 确保虚拟环境存在
  if [ ! -d ".venv" ]; then
    echo "创建 Python 虚拟环境..."
    python3 -m venv .venv
  fi

  # 激活虚拟环境并安装依赖
  source .venv/bin/activate
  pip install -e ".[dev]" --quiet

  # 安装 PyInstaller (如果未安装)
  pip install pyinstaller --quiet

  # 清理旧的构建
  rm -rf build dist

  # 执行打包
  echo "执行 PyInstaller 打包..."
  pyinstaller bridge.spec --clean --noconfirm

  if [ -f "dist/bridge" ] || [ -f "dist/bridge.exe" ]; then
    echo "✅ Python 后端打包完成"
  else
    echo "❌ Python 打包失败，请检查 bridge.spec"
    exit 1
  fi

  cd "$PROJECT_ROOT"
}

# 构建 Renderer
build_renderer() {
  echo ""
  echo "[4/5] 构建 Renderer..."

  cd "$PROJECT_ROOT/apps/renderer"
  npm run build
  cd "$PROJECT_ROOT"

  if [ -f "apps/renderer/dist/index.html" ]; then
    echo "✅ Renderer 构建完成"
  else
    echo "❌ Renderer 构建失败"
    exit 1
  fi
}

# 打包 Electron
package_electron() {
  echo ""
  echo "[5/5] 打包 Electron 应用..."

  cd "$PROJECT_ROOT/apps/electron"

  # 确保测试证书存在（Windows 签名需要）
  if [ "$PLATFORM" = "win" ] || [ "$PLATFORM" = "auto" ] && [ "$(uname -s 2>/dev/null || echo "MINGW")" = "MINGW"* ] || [ "$(uname -s 2>/dev/null)" = "MSYS"* ]; then
    echo "检查代码签名证书..."
    CERT_DIR="$PROJECT_ROOT/apps/electron/cert"
    CERT_PFX="$CERT_DIR/finance-assistant-test.pfx"
    if [ ! -f "$CERT_PFX" ]; then
      echo "未找到测试证书，正在生成..."
      powershell -ExecutionPolicy Bypass -File "$PROJECT_ROOT/apps/electron/scripts/generate-test-cert.ps1"
      if [ $? -ne 0 ]; then
        echo "❌ 证书生成失败，请手动运行: powershell -ExecutionPolicy Bypass -File apps/electron/scripts/generate-test-cert.ps1"
        exit 1
      fi
      echo "✅ 测试证书已生成"
    else
      echo "✅ 测试证书已存在: $CERT_PFX"
    fi
    # 导出绝对路径供 electron-builder 使用
    export CERT_FILE="$CERT_PFX"
    echo "证书路径: $CERT_FILE"
  fi

  # 编译 TypeScript
  npm run build

  # 根据平台执行打包
  case "$PLATFORM" in
    win)
      echo "打包 Windows exe..."
      npm run package
      ;;
    mac)
      echo "打包 macOS dmg..."
      npm run package -- --mac
      ;;
    linux)
      echo "打包 Linux..."
      npm run package -- --linux
      ;;
    *)
      echo "未知平台: $PLATFORM，执行默认打包..."
      npm run package
      ;;
  esac

  cd "$PROJECT_ROOT"

  echo ""
  echo "✅ 打包完成！输出目录: $(ls -d release/*/ 2>/dev/null || echo 'release/')"
}

# 主流程
main() {
  check_dependencies
  install_npm_deps
  package_python
  build_renderer
  package_electron

  echo ""
  echo "=========================================="
  echo "  🎉 打包成功！"
  echo "=========================================="
  echo "输出文件:"
  ls -lh release/ 2>/dev/null || echo "  release/ 目录不存在"
}

main
