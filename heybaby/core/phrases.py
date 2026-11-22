"""Normalize commands and recognize the wake phrase."""

import re

WAKE_PHRASE = "hey baby"


def normalize(text):
    return " ".join(re.findall(r"[a-z0-9]+", text.lower().replace("'", "")))


def wake_command(text):
    """None means no wake phrase; an empty string means wake and listen."""
    text = normalize(text)
    for phrase in (WAKE_PHRASE, "hey babay"):
        if text == phrase:
            return ""
        if text.startswith(phrase + " "):
            return text[len(phrase) + 1:]
    return None
