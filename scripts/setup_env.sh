#!/bin/bash

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
    echo "[setup] Creating Python virtual environment..."
    if command -v python3 &> /dev/null; then
        python3 -m venv .venv
    elif command -v python &> /dev/null; then
        python -m venv .venv
    else
        echo "[setup] Python not found. Please install Python 3."
        exit 1
    fi
fi

echo "[setup] Installing dependencies..."
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

echo "[setup] Environment setup complete."
