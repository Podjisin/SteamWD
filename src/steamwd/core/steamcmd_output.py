"""Parse steamcmd console output into structured events."""

import re
from dataclasses import dataclass

__all__ = [
    "GuardCodeRequested",
    "DownloadProgress",
    "ItemDownloaded",
    "ItemFailed",
    "LoginFailed",
    "OutputEvent",
    "PasswordRequested",
    "is_guard_prompt",
    "is_password_prompt",
    "parse_line",
]


@dataclass(frozen=True, slots=True)
class ItemDownloaded:
    """steamcmd reported a successful item download."""

    item_id: int
    path: str
    size: int


@dataclass(frozen=True, slots=True)
class ItemFailed:
    """steamcmd reported a failed item download."""

    item_id: int
    reason: str


@dataclass(frozen=True, slots=True)
class LoginFailed:
    """Logging in to Steam failed."""

    reason: str


@dataclass(frozen=True, slots=True)
class GuardCodeRequested:
    """steamcmd is waiting for a Steam Guard code."""


@dataclass(frozen=True, slots=True)
class PasswordRequested:
    """steamcmd is waiting for a password."""


@dataclass(frozen=True, slots=True)
class DownloadProgress:
    """steamcmd reported progress for one Workshop item."""

    item_id: int
    percent: int


OutputEvent = ItemDownloaded | ItemFailed | LoginFailed | GuardCodeRequested | PasswordRequested | DownloadProgress

_SUCCESS = re.compile(r'Success\. Downloaded item (\d+) to "(.+?)" \((\d+) bytes\)')
_FAILURE = re.compile(r"ERROR! Download item (\d+) failed \((.+?)\)")
_LOGIN_RESULT = re.compile(r"(?:FAILED|ERROR)\s*(?:login with result code\s*)?\(?([^()]+?)\)?\s*$")
_BARE_FAILURE = re.compile(r"^(?:FAILED|ERROR) \(([^()]+)\)$")
_GUARD_PROMPT = re.compile(r"(steam guard code|two-factor code|two factor code)\s*:?\s*$", re.IGNORECASE)
_PASSWORD_PROMPT = re.compile(r"password\s*:\s*$", re.IGNORECASE)
_PROGRESS = re.compile(r"(?:\[\s*(\d{1,3})%\].*?item\s+(\d+)|item\s+(\d+).*?\b(\d{1,3})%)", re.IGNORECASE)


def parse_line(line: str) -> OutputEvent | None:
    """Turn one line of steamcmd output into an event, if it is meaningful."""
    text = line.strip()
    if match := _SUCCESS.search(text):
        return ItemDownloaded(item_id=int(match.group(1)), path=match.group(2), size=int(match.group(3)))
    if match := _FAILURE.search(text):
        return ItemFailed(item_id=int(match.group(1)), reason=match.group(2))
    if match := _PROGRESS.search(text):
        percent = int(match.group(1) or match.group(4))
        item_id = int(match.group(2) or match.group(3))
        if 0 <= percent <= 100:
            return DownloadProgress(item_id=item_id, percent=percent)
    if is_guard_prompt(text):
        return GuardCodeRequested()
    if is_password_prompt(text):
        return PasswordRequested()
    if "Logging in user" in text and ("FAILED" in text or "ERROR" in text):
        match = _LOGIN_RESULT.search(text)
        return LoginFailed(reason=match.group(1).strip() if match else text)
    if "FAILED login with result code" in text:
        match = _LOGIN_RESULT.search(text)
        return LoginFailed(reason=match.group(1).strip() if match else text)
    if match := _BARE_FAILURE.match(text):
        return LoginFailed(reason=match.group(1).strip())
    return None


def is_guard_prompt(text: str) -> bool:
    """Whether the (possibly partial) output ends with a Steam Guard prompt."""
    return bool(_GUARD_PROMPT.search(text))


def is_password_prompt(text: str) -> bool:
    """Whether the (possibly partial) output ends with a password prompt."""
    return bool(_PASSWORD_PROMPT.search(text))
