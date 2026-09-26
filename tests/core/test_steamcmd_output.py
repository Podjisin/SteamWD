import pytest

from steamwd.core.steamcmd_output import (
    DownloadProgress,
    GuardCodeRequested,
    ItemDownloaded,
    ItemFailed,
    LoginFailed,
    PasswordRequested,
    parse_line,
)


def test_success_line() -> None:
    line = r'Success. Downloaded item 123 to "C:\cache\steamapps\workshop\content\4000\123" (98765 bytes)'
    assert parse_line(line) == ItemDownloaded(123, r"C:\cache\steamapps\workshop\content\4000\123", 98765)


def test_failure_line() -> None:
    assert parse_line("ERROR! Download item 456 failed (Access Denied).") == ItemFailed(456, "Access Denied")


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        ("Logging in user 'bob' [U:1:0] to Steam Public...FAILED (Invalid Password)", "Invalid Password"),
        ("FAILED (Rate Limit Exceeded)", "Rate Limit Exceeded"),
        ("FAILED login with result code Account Logon Denied", "Account Logon Denied"),
    ],
)
def test_login_failures(line: str, reason: str) -> None:
    assert parse_line(line) == LoginFailed(reason)


def test_prompts() -> None:
    assert parse_line("Steam Guard code:") == GuardCodeRequested()
    assert parse_line("Two-factor code:") == GuardCodeRequested()
    assert parse_line("password: ") == PasswordRequested()


def test_download_progress_line() -> None:
    assert parse_line("Downloading item 123... 42% (12.3 MB / 29.2 MB)") == DownloadProgress(123, 42)


def test_download_progress_accepts_steamcmd_bracket_format() -> None:
    assert parse_line("[ 73%] Downloading item 123") == DownloadProgress(123, 73)


@pytest.mark.parametrize(
    "line",
    [
        "Logging in user 'bob' [U:1:0] to Steam Public...OK",
        "Waiting for user info...OK",
        "Loading Steam API...OK",
        "",
    ],
)
def test_irrelevant_lines(line: str) -> None:
    assert parse_line(line) is None
