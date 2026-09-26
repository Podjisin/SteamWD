"""Well-known filesystem locations."""

import os
from pathlib import Path

__all__ = [
    "APP_DIR_NAME",
    "config_dir",
    "data_dir",
    "default_cache_dir",
    "default_log_dir",
    "default_output_dir",
    "default_steamcmd_path",
    "history_file",
    "settings_file",
]

APP_DIR_NAME = "SteamWD"


def config_dir() -> Path:
    """Roaming config folder: ``%APPDATA%\\SteamWD``."""
    base = os.environ.get("APPDATA")
    return (Path(base) if base else Path.home() / "AppData" / "Roaming") / APP_DIR_NAME


def data_dir() -> Path:
    """Local (non-roaming) data folder for large files: ``%LOCALAPPDATA%\\SteamWD``."""
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / "AppData" / "Local") / APP_DIR_NAME


def settings_file() -> Path:
    """Path of the settings JSON file."""
    return config_dir() / "settings.json"


def history_file() -> Path:
    """Path of the download history JSON file."""
    return config_dir() / "history.json"


def default_log_dir() -> Path:
    """Default folder for log files."""
    return config_dir() / "logs"


def default_steamcmd_path() -> Path:
    """Default location of ``steamcmd.exe`` (installed automatically if missing)."""
    return data_dir() / "steamcmd" / "steamcmd.exe"


def default_cache_dir() -> Path:
    """Default folder steamcmd downloads into before files are copied or moved."""
    return data_dir() / "cache"


def default_output_dir() -> Path:
    """Default folder for finished downloads."""
    return Path.home() / "Downloads" / APP_DIR_NAME
