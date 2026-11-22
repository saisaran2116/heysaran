#!/bin/bash
set -eu
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python=".hey-baby-venv/bin/python"
if [[ ! -x "$python" ]]; then
    echo "Hey Baby is not installed. Run: python3 setup.py" >&2
    exit 1
fi
exec "$python" hey_saran.py "$@"
