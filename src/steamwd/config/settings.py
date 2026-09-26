"""Application settings, defaults and validation.

Settings never contain secrets; passwords live in the Windows Credential Manager.
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields, replace
from typing import Any, cast

from steamwd.config import paths
from steamwd.core.naming import validate_template

__all__ = [
    "CHOICES",
    "NAMING_PRESETS",
    "PATH_FIELDS",
    "RANGES",
    "SCHEMA_VERSION",
    "Settings",
    "settings_from_dict",
    "settings_to_dict",
]

SCHEMA_VERSION = 1

CHOICES: dict[str, tuple[str, ...]] = {
    "transfer_mode": ("copy", "move", "leave"),
    "group_by": ("none", "appid", "game"),
    "login_mode": ("anonymous", "account"),
    "theme": ("light", "dark"),
    "log_level": ("DEBUG", "INFO", "WARNING", "ERROR"),
}

RANGES: dict[str, tuple[int, int]] = {
    "steamcmd_timeout_minutes": (1, 1440),
    "max_retries": (0, 10),
    "retry_delay_seconds": (0, 600),
    "batch_size": (1, 500),
    "api_timeout_seconds": (5, 300),
}

PATH_FIELDS = frozenset({"steamcmd_path", "cache_dir", "output_dir", "log_dir"})

NAMING_PRESETS = ("{title}", "{id} - {title}", "{title} ({id})", "{id}", "{game} - {title}")


@dataclass(frozen=True, slots=True)
class Settings:
    """All user-configurable options."""

    # steamcmd
    steamcmd_path: str = field(default_factory=lambda: str(paths.default_steamcmd_path()))
    auto_install_steamcmd: bool = True
    cache_dir: str = field(default_factory=lambda: str(paths.default_cache_dir()))
    validate_downloads: bool = False
    steamcmd_timeout_minutes: int = 120

    # Output
    output_dir: str = field(default_factory=lambda: str(paths.default_output_dir()))
    transfer_mode: str = "copy"
    clear_cache_after_copy: bool = True
    group_by: str = "none"
    naming_template: str = "{title}"
    skip_existing: bool = True
    expand_nested_collections: bool = True
    open_output_when_done: bool = False

    # Steam account
    login_mode: str = "anonymous"
    username: str = ""

    # Queue and network
    max_retries: int = 2
    retry_delay_seconds: int = 5
    batch_size: int = 25
    api_timeout_seconds: int = 30

    # Appearance and logging
    theme: str = "light"
    log_level: str = "INFO"
    log_dir: str = field(default_factory=lambda: str(paths.default_log_dir()))
    confirm_exit_while_running: bool = True


def settings_to_dict(settings: Settings) -> dict[str, Any]:
    """Serialize settings to a JSON-compatible dict."""
    return {"schema_version": SCHEMA_VERSION, **asdict(settings)}


def settings_from_dict(data: Mapping[str, object]) -> tuple[Settings, list[str]]:
    """Build settings from untrusted data, falling back to defaults for bad values.

    Args:
        data: Parsed JSON or values collected from the settings form.

    Returns:
        The settings and a list of warnings for values that were rejected.
    """
    defaults = Settings()
    accepted: dict[str, object] = {}
    warnings: list[str] = []
    for settings_field in fields(Settings):
        name = settings_field.name
        if name not in data:
            continue
        value = data[name]
        if isinstance(value, str):
            value = value.strip()
        error = _validate(name, value, getattr(defaults, name))
        if error:
            warnings.append(f"{name}: {error} (using default)")
        else:
            accepted[name] = value
    return replace(defaults, **cast(dict[str, Any], accepted)), warnings


def _validate(name: str, value: object, default: object) -> str | None:
    if isinstance(default, bool):
        return None if isinstance(value, bool) else "must be true or false"
    if isinstance(default, int):
        if isinstance(value, bool) or not isinstance(value, int):
            return "must be a whole number"
        low, high = RANGES[name]
        return None if low <= value <= high else f"must be between {low} and {high}"
    if not isinstance(value, str):
        return "must be text"
    if name in CHOICES and value not in CHOICES[name]:
        return f"must be one of {', '.join(CHOICES[name])}"
    if name in PATH_FIELDS and not value:
        return "must not be empty"
    if name == "naming_template":
        return validate_template(value)
    return None
