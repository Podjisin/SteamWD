"""Folder naming templates and Windows-safe file names."""

import re
import string

__all__ = ["TEMPLATE_FIELDS", "render_folder_name", "sanitize_filename", "validate_template"]

TEMPLATE_FIELDS = ("id", "title", "appid", "game")

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")
_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
)
MAX_NAME_LENGTH = 120


def validate_template(template: str) -> str | None:
    """Check a folder naming template.

    Args:
        template: A ``str.format`` style template such as ``"{id} - {title}"``.

    Returns:
        A human-readable error, or ``None`` if the template is valid.
    """
    if not template.strip():
        return "template is empty"
    try:
        parsed = list(string.Formatter().parse(template))
    except ValueError as exc:
        return f"invalid template ({exc})"
    used: set[str] = set()
    for _literal, field_name, format_spec, conversion in parsed:
        if field_name is None:
            continue
        if field_name not in TEMPLATE_FIELDS:
            allowed = ", ".join(f"{{{name}}}" for name in TEMPLATE_FIELDS)
            return f"unknown field {{{field_name}}}; allowed: {allowed}"
        if format_spec or conversion:
            return "format specifiers are not supported"
        used.add(field_name)
    if not used & {"id", "title"}:
        return "template must contain {id} or {title}"
    return None


def render_folder_name(template: str, *, item_id: int, title: str, app_id: int, game: str) -> str:
    """Render a folder name for an item, falling back to the ID if the result is empty."""
    name = template.format(id=item_id, title=title or str(item_id), appid=app_id, game=game or str(app_id))
    return sanitize_filename(name) or str(item_id)


def sanitize_filename(name: str, max_length: int = MAX_NAME_LENGTH) -> str:
    """Make a string safe to use as a single Windows path component."""
    cleaned = _INVALID_CHARS.sub("_", name)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip().rstrip(". ")
    cleaned = cleaned[:max_length].rstrip(". ")
    if cleaned.split(".")[0].upper() in _RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return cleaned
