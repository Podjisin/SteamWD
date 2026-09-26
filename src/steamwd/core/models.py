from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

__all__ = ["DownloadJob", "JobStatus", "WorkshopItem", "workshop_url"]


class JobStatus(StrEnum):
    QUEUED = "Queued"
    RESOLVING = "Resolving"
    DOWNLOADING = "Downloading"
    PROCESSING = "Processing"
    DONE = "Done"
    SKIPPED = "Skipped"
    FAILED = "Failed"
    CANCELLED = "Cancelled"

    @property
    def finished(self) -> bool:
        return self in _FINISHED

    @property
    def active(self) -> bool:
        return self in _ACTIVE


_FINISHED = frozenset({JobStatus.DONE, JobStatus.SKIPPED, JobStatus.FAILED, JobStatus.CANCELLED})
_ACTIVE = frozenset({JobStatus.RESOLVING, JobStatus.DOWNLOADING, JobStatus.PROCESSING})


@dataclass(frozen=True, slots=True)
class WorkshopItem:
    item_id: int
    title: str
    app_id: int
    file_size: int = 0
    time_updated: int = 0


@dataclass(slots=True)
class DownloadJob:
    """A single row in the download queue.

    Jobs are owned and mutated by the download worker. Copies are sent to the GUI.
    """

    item_id: int
    title: str = ""
    app_id: int | None = None
    file_size: int = 0
    time_updated: int = 0
    status: JobStatus = JobStatus.QUEUED
    message: str = ""
    progress: int | None = None
    attempts: int = 0
    is_collection: bool = False
    source_collection: int | None = None
    output_path: Path | None = None

    def apply_item(self, item: WorkshopItem) -> None:
        """Copy API metadata onto this job."""
        self.title = item.title
        self.app_id = item.app_id
        self.file_size = item.file_size
        self.time_updated = item.time_updated


def workshop_url(item_id: int) -> str:
    return f"https://steamcommunity.com/sharedfiles/filedetails/?id={item_id}"
