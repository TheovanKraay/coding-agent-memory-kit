#!/bin/bash
set -e
pip install -r "$(dirname "$0")/requirements.txt"
python "$(dirname "$0")/scripts/memory_cli.py" init
