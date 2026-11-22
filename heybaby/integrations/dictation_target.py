"""Bind optional macOS dictation insertion to a verified text selection."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Selection:
    element: object
    value: str
    range_value: object
    start: int
    length: int


def focused_selection():
    import ApplicationServices as ax

    if not ax.AXIsProcessTrusted():
        raise RuntimeError("Allow Hey Baby in Accessibility, or use Copy.")
    system = ax.AXUIElementCreateSystemWide()
    error, element = ax.AXUIElementCopyAttributeValue(system, "AXFocusedUIElement", None)
    if error or element is None:
        raise RuntimeError("Focus a supported text editor, or use Copy.")

    def read(attribute):
        status, value = ax.AXUIElementCopyAttributeValue(element, attribute, None)
        if status:
            raise RuntimeError("This field does not support verified insertion. Use Copy.")
        return value

    role = read("AXRole")
    subrole_status, subrole = ax.AXUIElementCopyAttributeValue(element, "AXSubrole", None)
    if (role not in {"AXTextArea", "AXTextField"} or subrole == "AXSecureTextField"
            or (role == "AXTextField" and subrole_status)):
        raise RuntimeError("This field does not support verified insertion. Use Copy.")
    status, writable = ax.AXUIElementIsAttributeSettable(element, "AXSelectedText", None)
    if status or not writable:
        raise RuntimeError("This field does not support verified insertion. Use Copy.")
    value = read("AXValue")
    range_value = read("AXSelectedTextRange")
    try:
        valid, span = ax.AXValueGetValue(range_value, ax.kAXValueCFRangeType, None)
    except (TypeError, ValueError):
        valid = False
    if not valid or not isinstance(value, str):
        raise RuntimeError("This field does not support verified insertion. Use Copy.")
    start, length = span
    if start < 0 or length < 0 or 2 * (start + length) > len(value.encode("utf-16-le")):
        raise RuntimeError("This field does not support verified insertion. Use Copy.")
    return Selection(element, value, range_value, start, length)


def insert(selection, text):
    import ApplicationServices as ax

    from CoreFoundation import CFEqual

    current = focused_selection()
    if (not CFEqual(selection.element, current.element) or selection.value != current.value
            or not CFEqual(selection.range_value, current.range_value)):
        raise RuntimeError("The original field or selection changed. Use Copy.")
    previous = current.value.encode("utf-16-le")
    expected = (previous[:2 * current.start] + text.encode("utf-16-le")
                + previous[2 * (current.start + current.length):])
    if ax.AXUIElementSetAttributeValue(current.element, "AXSelectedText", text):
        raise RuntimeError("Insertion was not confirmed. Review the editor before pasting.")
    error, value = ax.AXUIElementCopyAttributeValue(current.element, "AXValue", None)
    if error or not isinstance(value, str) or value.encode("utf-16-le") != expected:
        raise RuntimeError("Insertion was not confirmed. Review the editor before pasting.")
