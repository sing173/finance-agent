@echo off
setlocal

REM Finance Assistant Package Script (Windows)
REM Usage: package.bat [win|mac|linux]

set PLATFORM=%1
if "%PLATFORM%"=="" set PLATFORM=win

echo ==========================================
echo   Finance Assistant Package Script (Windows)
echo ==========================================
echo Target platform: %PLATFORM%
echo.

REM Change to project root
cd /d "%~dp0\.."

REM Check dependencies
echo [1/5] Checking dependencies...
where node >nul 2>&1
if errorlevel 1 (
  echo [X] Node.js not found, please install Node.js ^>= 18
  exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
  echo [X] Python not found, please install Python ^>= 3.11
  exit /b 1
)

echo [OK] Node.js:
node --version
echo [OK] Python:
python --version
echo.

REM Install npm dependencies
echo [2/5] Installing npm dependencies...
call npm install
if errorlevel 1 (
  echo [X] npm install failed
  exit /b 1
)
echo [OK] npm dependencies installed
echo.

REM Package Python backend
echo [3/5] Packaging Python backend...
cd apps\python

if not exist ".venv\" (
  echo Creating Python virtual environment...
  python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install Python dependencies
pip install -e ".[dev]" -q
pip install pyinstaller -q

REM Clean old builds
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Run PyInstaller
echo Running PyInstaller...
pyinstaller bridge.spec --clean --noconfirm

if exist "dist\bridge.exe" (
  echo [OK] Python backend packaged
) else (
  echo [X] Python packaging failed
  exit /b 1
)

cd ..\..

echo.

REM Build Renderer
echo [4/5] Building Renderer...
cd apps\renderer
call npm run build
if errorlevel 1 (
  echo [X] Renderer build failed
  exit /b 1
)
cd ..\..
echo [OK] Renderer built
echo.

REM Package Electron
echo [5/5] Packaging Electron application...
cd apps\electron

REM Compile TypeScript
call npm run build

REM Package by platform
if "%PLATFORM%"=="win" (
  echo Packaging for Windows ^(NSIS^)...
  call npm run package -- --win
) else if "%PLATFORM%"=="mac" (
  echo Packaging for macOS...
  call npm run package -- --mac
) else if "%PLATFORM%"=="linux" (
  echo Packaging for Linux...
  call npm run package -- --linux
) else (
  echo Unknown platform: %PLATFORM%, using default...
  call npm run package
)

cd ..\..

echo.
echo ==========================================
echo   [DONE] Packaging completed!
echo ==========================================
echo Output files:
if exist release\ dir /b release\ 2>nul || echo  release\ directory not found

endlocal
