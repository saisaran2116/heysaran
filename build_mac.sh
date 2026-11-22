#!/bin/bash
set -eu
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ "$(uname -s)" != Darwin ]]; then
    echo "Build the Mac app on macOS." >&2
    exit 1
fi
python=".hey-baby-venv/bin/python"
"$python" -c 'from heybaby.integrations.speech import DEFAULT_MODEL; assert (DEFAULT_MODEL / "conf/model.conf").is_file(), "Run setup.py to install the speech model."'
PYTHONPATH="$PWD" PYINSTALLER_CONFIG_DIR="$PWD/build/cache" \
    "$python" -m PyInstaller --noconfirm HeyBaby.spec
codesign --verify --deep --strict "dist/Hey Baby.app"
