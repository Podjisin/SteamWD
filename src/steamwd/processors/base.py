"""Interface shared by game-specific content processors."""

from pathlib import Path
from typing import Protocol

from steamwd.config.settings import Settings
from steamwd.core.models import WorkshopItem


class ModProcessor(Protocol):
    """Processes one downloaded Workshop item into its game-specific format."""

    def process(self, source: Path, item: WorkshopItem, settings: Settings, destination: Path) -> Path: ...
