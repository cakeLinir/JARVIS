@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
set "AGENT_DIR=%REPO_ROOT%\desktop-agent"

if not exist "%AGENT_DIR%\src\main.py" (
  echo [ERROR] desktop-agent\src\main.py nicht gefunden.
  exit /b 2
)

pushd "%AGENT_DIR%" >nul 2>nul
py -3 src\main.py
set EXIT_CODE=%ERRORLEVEL%
popd >nul 2>nul

exit /b %EXIT_CODE%
