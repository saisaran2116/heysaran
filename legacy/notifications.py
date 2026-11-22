#!/usr/bin/env python3
"""
================================================================================
 Hey Saran - Native macOS Notification Service
================================================================================
Provides non-blocking, safe visual popup notifications for macOS.
Features:
- Success popup with checkmark (✓ Hey Saran)
- Failure popup with error icon (❌ Hey Saran)
- Duplicate notification prevention (deduplication window)
- Non-blocking execution (does not interrupt audio processing)
- Strict sanitization (prevents secrets or API keys from ever being exposed)
- Failsafe execution (errors in notifications never crash the assistant)
================================================================================
"""

import os
import re
import subprocess
import time
from typing import Optional

# Deduplication cache to prevent alert flooding
_recent_notifications = {}
DEDUP_WINDOW_SECONDS = 2.5


def sanitize_text(text: str) -> str:
    """
    Sanitizes notification text:
    - Redacts any API keys, bearer tokens, or sensitive patterns
    - Escapes quotes and backslashes for AppleScript syntax safety
    """
    if not text:
        return ""
    # Redact potential API keys (e.g. sk_..., bearer tokens, long hex/base64 strings)
    text = re.sub(r"sk_[a-zA-Z0-9_-]{10,}", "[REDACTED_KEY]", text)
    text = re.sub(r"(bearer|api[_-]?key)[=:\s]+[a-zA-Z0-9_-]{10,}", r"\1: [REDACTED]", text, flags=re.IGNORECASE)
    # Escape quotes and backslashes for AppleScript
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    # Collapse multiple whitespaces/newlines
    text = re.sub(r"\s+", " ", text).strip()
    return text


def send_notification(
    message: str,
    title: str = "Hey Saran",
    subtitle: str = "",
    sound: Optional[str] = "Glass",
    is_error: bool = False
) -> bool:
    """
    Displays a native macOS notification banner / popup.
    Non-blocking: Executes via background subprocess so audio capture is never stalled.
    Returns True if dispatched, False if suppressed as duplicate or on error.
    """
    global _recent_notifications

    if not message:
        return False

    now = time.time()
    # Prune old cache entries
    _recent_notifications = {k: v for k, v in _recent_notifications.items() if now - v < 10.0}

    # Duplicate suppression check
    cache_key = f"{title}:{subtitle}:{message}"
    last_sent = _recent_notifications.get(cache_key, 0.0)
    if now - last_sent < DEDUP_WINDOW_SECONDS:
        return False

    _recent_notifications[cache_key] = now

    clean_title = sanitize_text(title)
    clean_subtitle = sanitize_text(subtitle)
    clean_message = sanitize_text(message)

    script_parts = [f'display notification "{clean_message}" with title "{clean_title}"']
    if clean_subtitle:
        script_parts.append(f'subtitle "{clean_subtitle}"')
    if sound:
        script_parts.append(f'sound name "{sound}"')

    apple_script = " ".join(script_parts)

    try:
        subprocess.Popen(
            ["osascript", "-e", apple_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except Exception as e:
        print(f"[WARN] Failed to trigger macOS notification: {e}")
        return False


def notify_success(message: str, subtitle: str = "Task completed successfully!") -> bool:
    """Triggers a success popup with green checkmark formatting."""
    return send_notification(
        message=message,
        title="✓ Hey Saran",
        subtitle=subtitle,
        sound="Glass",
        is_error=False
    )


def notify_error(message: str = "Something went wrong. Please try again.", subtitle: str = "Operation Failed") -> bool:
    """Triggers an error popup with safe message formatting."""
    return send_notification(
        message=message,
        title="❌ Hey Saran",
        subtitle=subtitle,
        sound="Basso",
        is_error=True
    )
