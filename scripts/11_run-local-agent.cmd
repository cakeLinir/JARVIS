@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
set "AGENT_DIR=%REPO_ROOT%\desktop-agent"
set "VENV_PYTHON=%REPO_ROOT%\.venv\Scripts\python.exe"

if not exist "%AGENT_DIR%\src\main.py" (
  echo [ERROR] desktop-agent\src\main.py nicht gefunden.
  exit /b 2
)

if exist "%VENV_PYTHON%" (
  set "PYTHON=%VENV_PYTHON%"
  echo [INFO] .venv Python: %VENV_PYTHON%
) else (
  set "PYTHON=py -3"
  echo [WARN] .venv nicht gefunden, nutze System-Python.
)

pushd "%AGENT_DIR%" >nul 2>nul
%PYTHON% src\main.py
set EXIT_CODE=%ERRORLEVEL%
popd >nul 2>nul

exit /b %EXIT_CODE%
