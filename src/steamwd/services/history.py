"""Persistent record of downloaded items (used to skip up-to-date items)."""

import logging
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from steamwd.config.store import read_json, write_json_atomic

__all__ = ["DownloadHistory", "HistoryEntry"]

logger = logging.getLogger(__name__)
_VERSION = 1


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """A downloaded item."""

    item_id: int
    title: str
    app_id: int
    time_updated: int
    path: str
    downloaded_at: float


class DownloadHistory:
    """JSON-backed download history."""

    def __init__(self, path: Path) -> None:
        """Create a history stored at ``path`` and load existing entries."""
        self._path = path
        self._entries: dict[int, HistoryEntry] = {}
        self.load()

    def load(self) -> None:
        """Load entries from disk; unreadable files are logged and ignored."""
        self._entries.clear()
        if not self._path.exists():
            return
        try:
            data = read_json(self._path)
            for raw in data.get("items", {}).values():
                entry = HistoryEntry(
                    item_id=int(raw["item_id"]),
                    title=str(raw["title"]),
                    app_id=int(raw["app_id"]),
                    time_updated=int(raw["time_updated"]),
                    path=str(raw["path"]),
                    downloaded_at=float(raw["downloaded_at"]),
                )
                self._entries[entry.item_id] = entry
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            logger.warning("Ignoring unreadable download history %s: %s", self._path, exc)

    def get(self, item_id: int) -> HistoryEntry | None:
        """Return the entry for an item, if any."""
        return self._entries.get(item_id)

    def owner_of(self, path: Path) -> int | None:
        """Return the item ID recorded for a folder, if any."""
        wanted = _normalize(path)
        for entry in self._entries.values():
            if _normalize(Path(entry.path)) == wanted:
                return entry.item_id
        return None

    def record(self, *, item_id: int, title: str, app_id: int, time_updated: int, path: Path) -> None:
        """Record a finished download and save to disk."""
        self._entries[item_id] = HistoryEntry(
            item_id=item_id,
            title=title,
            app_id=app_id,
            time_updated=time_updated,
            path=str(path),
            downloaded_at=time.time(),
        )
        self.save()

    def save(self) -> None:
        """Write the history to disk (errors are logged, not raised)."""
        data = {"version": _VERSION, "items": {str(k): asdict(v) for k, v in self._entries.items()}}
        try:
            write_json_atomic(self._path, data)
        except OSError as exc:
            logger.warning("Could not save download history: %s", exc)


def _normalize(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))
