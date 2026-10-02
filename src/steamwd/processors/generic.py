"""Default processor for games without specialized support."""

from pathlib import Path

from steamwd.config.settings import Settings
from steamwd.core.models import WorkshopItem
from steamwd.services import files


class GenericProcessor:
    def process(self, source: Path, item: WorkshopItem, settings: Settings, destination: Path) -> Path:
        """Copy, move, or leave the item using the existing generic behavior."""
        if settings.transfer_mode == "leave":
            return source
        return files.transfer(source, destination, settings.transfer_mode)
