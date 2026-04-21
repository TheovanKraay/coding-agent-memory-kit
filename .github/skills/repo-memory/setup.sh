#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing dependencies..."
pip install -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "Running initialization..."
python "$SCRIPT_DIR/scripts/memory_init.py"
