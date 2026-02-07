@echo off
setlocal

cd /d "%~dp0.."

if not exist ".venv" (
    echo [setup] Creating Python virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [setup] Failed to create venv. Please check your python installation.
        exit /b 1
    )
)

echo [setup] Installing dependencies...
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt
if errorlevel 1 (
    echo [setup] Failed to install dependencies.
    exit /b 1
)

echo [setup] Environment setup complete.
endlocal
