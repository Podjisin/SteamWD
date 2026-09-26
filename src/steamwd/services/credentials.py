"""Store Steam passwords in the Windows Credential Manager."""

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from steamwd.errors import CredentialError

__all__ = ["SERVICE_NAME", "CredentialStore"]

SERVICE_NAME = "SteamWD"


def _use_windows_backend() -> None:
    """Pin the Windows Credential Manager backend (entry-point discovery is unreliable when frozen)."""
    try:
        from keyring.backends.Windows import WinVaultKeyring

        keyring.set_keyring(WinVaultKeyring())  # type: ignore[no-untyped-call]
    except Exception:  # noqa: BLE001 - fall back to keyring's own discovery
        pass


class CredentialStore:
    """Save, read and delete Steam account passwords."""

    def __init__(self, service: str = SERVICE_NAME) -> None:
        """Create a store using the given Credential Manager service name."""
        self._service = service
        _use_windows_backend()

    def get_password(self, username: str) -> str | None:
        """Return the saved password for ``username`` or ``None``."""
        try:
            return keyring.get_password(self._service, _key(username))
        except KeyringError as exc:
            raise CredentialError(f"Could not read the saved password: {exc}") from exc

    def set_password(self, username: str, password: str) -> None:
        """Save a password for ``username``."""
        try:
            keyring.set_password(self._service, _key(username), password)
        except KeyringError as exc:
            raise CredentialError(f"Could not save the password: {exc}") from exc

    def delete_password(self, username: str) -> None:
        """Delete the saved password for ``username`` (no error if none is saved)."""
        try:
            keyring.delete_password(self._service, _key(username))
        except PasswordDeleteError:
            pass
        except KeyringError as exc:
            raise CredentialError(f"Could not delete the password: {exc}") from exc


def _key(username: str) -> str:
    return f"steam:{username.strip().lower()}"
