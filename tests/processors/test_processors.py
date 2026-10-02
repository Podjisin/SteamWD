from pathlib import Path

from steamwd.config.settings import Settings
from steamwd.core.models import WorkshopItem
from steamwd.processors import processor_for, processor_name


def test_unknown_game_uses_generic_processor(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "mod.txt").write_text("content", encoding="utf-8")

    destination = processor_for(4000).process(
        source,
        WorkshopItem(1, "Example", 4000),
        Settings(output_dir=str(tmp_path / "out")),
        tmp_path / "out" / "Example",
    )

    assert destination == tmp_path / "out" / "Example"
    assert (destination / "mod.txt").read_text(encoding="utf-8") == "content"


def test_stellaris_processor_creates_mod_descriptor(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "descriptor.mod").write_text(
        'version="3.40.2"\ntags={\n\t"Gameplay"\n}\nname="My Stellaris Mod"\nsupported_version="v4.5.*"\nremote_file_id="old"\n',
        encoding="utf-8",
    )
    mod_dir = tmp_path / "Paradox" / "mod"
    settings = Settings(stellaris_mod_dir=str(mod_dir))

    destination = processor_for(281990).process(
        source,
        WorkshopItem(123, "My Stellaris Mod", 281990),
        settings,
        tmp_path / "out" / "ignored",
    )

    assert destination == mod_dir / "My Stellaris Mod"
    descriptor = mod_dir / "My Stellaris Mod.mod"
    assert (destination / "descriptor.mod").exists()
    assert 'remote_file_id="old"' in (destination / "descriptor.mod").read_text(encoding="utf-8")
    descriptor_text = descriptor.read_text(encoding="utf-8")
    assert descriptor_text == (
        'version="3.40.2"\n'
        "tags={\n"
        '\t"Gameplay"\n'
        "}\n"
        'name="My Stellaris Mod"\n'
        'supported_version="v4.5.*"\n'
        f'path="{destination.as_posix()}"\n'
        'remote_file_id="123"\n'
    )


def test_rimworld_processor_places_mod_without_rewriting_metadata(tmp_path: Path) -> None:
    source = tmp_path / "source"
    about = source / "About"
    about.mkdir(parents=True)
    (about / "About.xml").write_text("<ModMetaData />", encoding="utf-8")
    mod_dir = tmp_path / "RimWorld" / "Mods"
    settings = Settings(rimworld_mod_dir=str(mod_dir))

    destination = processor_for(294100).process(
        source,
        WorkshopItem(456, "Vanilla Expanded", 294100),
        settings,
        tmp_path / "out" / "ignored",
    )

    assert destination == mod_dir / "Vanilla Expanded"
    assert (destination / "About" / "About.xml").read_text(encoding="utf-8") == "<ModMetaData />"


def test_processor_names_are_user_facing() -> None:
    assert processor_name(281990) == "Stellaris"
    assert processor_name(294100) == "RimWorld"
    assert processor_name(4000) == "Generic"
