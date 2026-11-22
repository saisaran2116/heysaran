#!/bin/bash
set -eu
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ "$(uname -s)" != Darwin ]]; then
    echo "This login launcher is for macOS." >&2
    exit 1
fi
if [[ ! -x .hey-baby-venv/bin/python ]]; then
    echo "Run setup.py and open Hey_Baby.command once before enabling login launch." >&2
    exit 1
fi
label="com.saran.heysaran"
launcher="$PWD/start.sh"
if [[ -x "$PWD/dist/Hey Baby.app/Contents/MacOS/HeyBaby" ]]; then
    launcher="$PWD/dist/Hey Baby.app/Contents/MacOS/HeyBaby"
    "$launcher" --check-model
fi
agent="$HOME/Library/LaunchAgents/$label.plist"
domain="gui/$(id -u)"
mkdir -p "$HOME/Library/LaunchAgents" "$PWD/logs"
if launchctl print "$domain/$label" >/dev/null 2>&1; then
    launchctl bootout "$domain/$label"
fi
# Generate XML via plistlib so spaces and XML special characters in paths work.
.hey-baby-venv/bin/python - "$agent" "$PWD" "$label" "$launcher" <<'PY'
import plistlib
import sys
from pathlib import Path

agent, root, label, launcher = sys.argv[1:]
with open(agent, "wb") as plist:
    plistlib.dump({
        "Label": label,
        "ProgramArguments": [launcher, "--background"],
        "WorkingDirectory": root,
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(Path(root) / "logs/service_output.log"),
        "StandardErrorPath": str(Path(root) / "logs/service_error.log"),
    }, plist)
PY
launchctl bootstrap "$domain" "$agent"
echo "Hey Baby is set to launch when you sign in."
