#!/bin/bash
set -eu
label="com.saran.heysaran"
domain="gui/$(id -u)"
if launchctl print "$domain/$label" >/dev/null 2>&1; then
    launchctl bootout "$domain/$label"
fi
rm -f "$HOME/Library/LaunchAgents/$label.plist"
echo "Hey Baby will no longer start at sign-in."
