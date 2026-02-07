#!/bin/bash
cd "$(dirname "$0")/.."

PYTHON_EXEC="python3"
if [ -f ".venv/bin/python" ]; then
    PYTHON_EXEC=".venv/bin/python"
fi

"$PYTHON_EXEC" src/main.py "$@"
