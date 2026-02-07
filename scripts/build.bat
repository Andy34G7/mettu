@echo off
setlocal
cd /d "%~dp0.."

set PYTHON_EXEC=python
if exist ".venv\Scripts\python.exe" (
    set PYTHON_EXEC=.venv\Scripts\python.exe
)

"%PYTHON_EXEC%" src/main.py %*
endlocal
