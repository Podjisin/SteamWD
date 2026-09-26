import json
from pathlib import Path

import pytest

from steamwd.config.settings import Settings, settings_from_dict, settings_to_dict
from steamwd.config.store import SettingsStore, export_settings, import_settings
from steamwd.errors import SettingsError


def test_round_trip(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(theme="dark", max_retries=5, naming_template="{id} - {title}", login_mode="account")
    store.save(settings)
    loaded, warnings = store.load()
    assert loaded == settings
    assert warnings == []


def test_missing_file_gives_defaults(tmp_path: Path) -> None:
    assert SettingsStore(tmp_path / "nope.json").load() == (Settings(), [])


def test_invalid_values_fall_back_with_warnings() -> None:
    settings, warnings = settings_from_dict(
        {
            "theme": "purple",
            "max_retries": 99,
            "batch_size": True,
            "skip_existing": "yes",
            "naming_template": "{nope}",
            "output_dir": "",
            "unknown_key": 1,
            "username": "  bob  ",
        }
    )
    defaults = Settings()
    assert settings.theme == defaults.theme
    assert settings.max_retries == defaults.max_retries
    assert settings.batch_size == defaults.batch_size
    assert settings.skip_existing == defaults.skip_existing
    assert settings.naming_template == defaults.naming_template
    assert settings.output_dir == defaults.output_dir
    assert settings.username == "bob"
    assert len(warnings) == 6


def test_corrupt_file_is_backed_up(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    settings, warnings = SettingsStore(path).load()
    assert settings == Settings()
    assert warnings
    assert (tmp_path / "settings.json.bak").exists()


def test_serialized_settings_contain_no_secret_fields() -> None:
    keys = set(settings_to_dict(Settings()))
    assert not {k for k in keys if "password" in k or "key" in k or "token" in k}


def test_export_and_import(tmp_path: Path) -> None:
    path = tmp_path / "export.json"
    export_settings(path, Settings(batch_size=3))
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1
    assert import_settings(path)[0].batch_size == 3


def test_import_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(SettingsError):
        import_settings(path)
