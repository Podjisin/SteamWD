"""Load and save settings as JSON."""

import json
import logging
from pathlib import Path
from typing import Any

from steamwd.config.settings import Settings, settings_from_dict, settings_to_dict
from steamwd.errors import SettingsError

__all__ = ["SettingsStore", "export_settings", "import_settings", "read_json", "write_json_atomic"]

logger = logging.getLogger(__name__)


def write_json_atomic(path: Path, data: Any) -> None:
    """Write JSON to ``path`` via a temporary file so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> Any:
    """Read and parse a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


class SettingsStore:
    """Persists :class:`Settings` to a JSON file."""

    def __init__(self, path: Path) -> None:
        """Create a store for the given settings file."""
        self.path = path

    def load(self) -> tuple[Settings, list[str]]:
        """Load settings; never raises. Returns settings plus warnings about rejected values."""
        if not self.path.exists():
            return Settings(), []
        try:
            data = read_json(self.path)
            if not isinstance(data, dict):
                raise ValueError("top-level value is not an object")
        except (OSError, ValueError) as exc:
            backup = self.path.with_name(f"{self.path.name}.bak")
            try:
                self.path.replace(backup)
            except OSError:
                logger.exception("Could not back up unreadable settings file")
            return Settings(), [f"Settings file was unreadable ({exc}). Defaults are used; old file saved as {backup}."]
        return settings_from_dict(data)

    def save(self, settings: Settings) -> None:
        """Save settings, raising :class:`SettingsError` on failure."""
        try:
            write_json_atomic(self.path, settings_to_dict(settings))
        except OSError as exc:
            raise SettingsError(f"Could not save settings to {self.path}: {exc}") from exc


def export_settings(path: Path, settings: Settings) -> None:
    """Export settings to a user-chosen file. Settings never include secrets."""
    try:
        write_json_atomic(path, settings_to_dict(settings))
    except OSError as exc:
        raise SettingsError(f"Could not export settings: {exc}") from exc


def import_settings(path: Path) -> tuple[Settings, list[str]]:
    """Import settings from a file, raising :class:`SettingsError` if it cannot be read."""
    try:
        data = read_json(path)
    except (OSError, ValueError) as exc:
        raise SettingsError(f"Could not read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SettingsError(f"{path} does not contain a settings object")
    return settings_from_dict(data)
