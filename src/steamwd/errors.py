"""Exception hierarchy for SteamWD."""

__all__ = [
    "CredentialError",
    "LoginError",
    "SettingsError",
    "SteamApiError",
    "SteamCmdError",
    "SteamWDError",
]


class SteamWDError(Exception):
    """Base class for all expected SteamWD errors."""


class SteamCmdError(SteamWDError):
    """steamcmd could not be installed, started or understood."""


class LoginError(SteamCmdError):
    """Logging in to Steam failed."""


class SteamApiError(SteamWDError):
    """The Steam Web API request failed or returned unexpected data."""


class SettingsError(SteamWDError):
    """Settings could not be read, written or validated."""


class CredentialError(SteamWDError):
    """The Windows Credential Manager could not be accessed."""
