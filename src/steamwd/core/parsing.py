import re
from dataclasses import dataclass, field

__all__ = ["ParseResult", "parse_workshop_ids"]

_QUERY_ID = re.compile(r"[?&]id=(\d+)", re.IGNORECASE)
_STEAM_PROTOCOL = re.compile(r"CommunityFilePage/(\d+)", re.IGNORECASE)
_SEPARATORS = re.compile(r"[\s,;]+")


@dataclass(frozen=True, slots=True)
class ParseResult:
    ids: list[int] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)


def parse_workshop_ids(text: str) -> ParseResult:
    """Extract Workshop item or collection IDs from free-form text.

    Accepts plain numeric IDs, ``steamcommunity.com`` URLs containing ``?id=``,
    and ``steam://url/CommunityFilePage/<id>`` links, separated by whitespace,
    commas or semicolons. Duplicates are removed while preserving order.

    Args:
        text: Text pasted by the user.

    Returns:
        The unique IDs found and any tokens that could not be understood.
    """
    ids: list[int] = []
    seen: set[int] = set()
    invalid: list[str] = []
    for token in _SEPARATORS.split(text.strip()):
        if not token:
            continue
        item_id = _token_to_id(token)
        if item_id is None:
            invalid.append(token)
        elif item_id not in seen:
            seen.add(item_id)
            ids.append(item_id)
    return ParseResult(ids=ids, invalid=invalid)


def _token_to_id(token: str) -> int | None:
    if token.isdigit():
        value = int(token)
        return value if value > 0 else None
    for pattern in (_QUERY_ID, _STEAM_PROTOCOL):
        match = pattern.search(token)
        if match:
            return int(match.group(1))
    return None
