"""Processor for RimWorld user Workshop mods."""

from pathlib import Path

from steamwd.config.settings import Settings
from steamwd.core.models import WorkshopItem
from steamwd.core.naming import sanitize_filename
from steamwd.services import files


class RimWorldProcessor:
    """Install a Workshop mod into RimWorld's user ``Mods`` folder."""

    def process(self, source: Path, item: WorkshopItem, settings: Settings, destination: Path) -> Path:
        """Copy or move the complete mod, including its ``About`` metadata."""
        mod_name = sanitize_filename(item.title) or str(item.item_id)
        destination = Path(settings.rimworld_mod_dir) / mod_name
        if settings.transfer_mode == "leave":
            return source
        return files.transfer(source, destination, settings.transfer_mode)
