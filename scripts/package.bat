@echo off
setlocal enabledelayedexpansion

REM Finance Assistant 一键打包脚本 (Windows)
REM 用法: package.bat [win|mac|linux]

set PLATFORM=%1
if "%PLATFORM%"=="" set PLATFORM=win

echo ==========================================
echo   Finance Assistant 打包脚本 (Windows)
echo ==========================================
echo 目标平台: %PLATFORM%
echo.

REM 进入项目根目录
cd /d "%~dp0\.."

REM 检查依赖
echo [1/5] 检查依赖...
where node >nul 2>&1
if errorlevel 1 (
  echo ❌ Node.js 未安装，请先安装 Node.js ^>= 18
  exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
  echo ❌ Python3 未安装，请先安装 Python ^>= 3.11
  exit /b 1
)

echo ✅ Node.js:
node --version
echo ✅ Python:
python --version
echo.

REM 安装 npm 依赖
echo [2/5] 安装 npm 依赖...
call npm install
if errorlevel 1 (
  echo ❌ npm 依赖安装失败
  exit /b 1
)
echo ✅ npm 依赖安装完成
echo.

REM 打包 Python 后端
echo [3/5] 打包 Python 后端...
cd apps\python

if not exist ".venv\" (
  echo 创建 Python 虚拟环境...
  python -m venv .venv
)

REM 激活虚拟环境
call .venv\Scripts\activate.bat

REM 安装 Python 依赖
pip install -e ".[dev]" -q
pip install pyinstaller -q

REM 清理旧构建
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM 执行打包
echo 执行 PyInstaller 打包...
pyinstaller bridge.spec --clean --noconfirm

if exist "dist\bridge.exe" (
  echo ✅ Python 后端打包完成
) else (
  echo ❌ Python 打包失败
  exit /b 1
)

cd ..\..

echo.

REM 构建 Renderer
echo [4/5] 构建 Renderer...
cd apps\renderer
call npm run build
if errorlevel 1 (
  echo ❌ Renderer 构建失败
  exit /b 1
)
cd ..\..
echo ✅ Renderer 构建完成
echo.

REM 打包 Electron
echo [5/5] 打包 Electron 应用...
cd apps\electron

REM 编译 TypeScript
call npm run build

REM 根据平台打包
if "%PLATFORM%"=="win" (
  echo 打包 Windows exe...
  call npm run package -- --win
) else if "%PLATFORM%"=="mac" (
  echo 打包 macOS dmg...
  call npm run package -- --mac
) else if "%PLATFORM%"=="linux" (
  echo 打包 Linux...
  call npm run package -- --linux
) else (
  echo 未知平台: %PLATFORM%，执行默认打包...
  call npm run package
)

cd ..\..

echo.
echo ==========================================
echo   🎉 打包完成！
echo ==========================================
echo 输出文件:
dir /b release\ 2>nul || echo  release\ 目录不存在

endlocal
