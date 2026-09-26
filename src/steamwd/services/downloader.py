"""Orchestrates a download run: resolve collections, fetch metadata, run steamcmd, place files."""

import dataclasses
import logging
import threading
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from steamwd.config.settings import Settings
from steamwd.core.models import DownloadJob, JobStatus, WorkshopItem
from steamwd.core.naming import render_folder_name, sanitize_filename
from steamwd.core.steamcmd_output import DownloadProgress, ItemDownloaded, ItemFailed, LoginFailed
from steamwd.errors import LoginError, SteamCmdError, SteamWDError
from steamwd.logging_setup import Redactor
from steamwd.services import files
from steamwd.services.history import DownloadHistory
from steamwd.services.steam_api import COLLECTION_FILE_TYPE
from steamwd.services.steamcmd import RunOutcome, SteamLogin

__all__ = ["DownloadEvent", "DownloadManager", "GuardCodeProvider", "JobChanged", "RunFinished"]

logger = logging.getLogger(__name__)

_FAILURE_HINTS = {
    "failure": "the game may require logging in with an account that owns it",
    "access denied": "the game may require logging in with an account that owns it",
    "timeout": "steamcmd timed out; large items often succeed on retry",
    "no connection": "check your internet connection",
}


@dataclass(frozen=True, slots=True)
class JobChanged:
    """A job was created or changed. ``job`` is a snapshot copy."""

    job: DownloadJob


@dataclass(frozen=True, slots=True)
class RunFinished:
    """A run ended."""

    done: int
    skipped: int
    failed: int
    cancelled: int


DownloadEvent = JobChanged | RunFinished
GuardCodeProvider = Callable[[str], str | None]


class SteamCmdRunner(Protocol):
    """The parts of :class:`steamwd.services.steamcmd.SteamCmd` the manager uses."""

    def is_installed(self) -> bool: ...  # noqa: D102

    def install(self, cancel: threading.Event, http_timeout: float = ...) -> None: ...  # noqa: D102

    def build_download_args(  # noqa: D102
        self, *, install_dir: Path, login: SteamLogin, items: Sequence[tuple[int, int]], validate: bool
    ) -> list[str]: ...

    def run(self, args: Sequence[str], cancel: threading.Event) -> RunOutcome: ...  # noqa: D102


class WorkshopApi(Protocol):
    """The parts of :class:`steamwd.services.steam_api.SteamApi` the manager uses."""

    def get_item_details(  # noqa: D102
        self, item_ids: Sequence[int]
    ) -> tuple[dict[int, WorkshopItem], dict[int, str]]: ...

    def get_collection_children(self, item_ids: Sequence[int]) -> dict[int, list[tuple[int, int]]]: ...  # noqa: D102

    def get_app_name(self, app_id: int) -> str | None: ...  # noqa: D102


class DownloadManager:
    """Runs one batch of downloads on a worker thread.

    Create a new manager for every run so it always uses the current settings.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        steamcmd: SteamCmdRunner,
        api: WorkshopApi,
        history: DownloadHistory,
        password: str | None,
        redactor: Redactor,
        emit: Callable[[DownloadEvent], None],
        guard_code_provider: GuardCodeProvider,
    ) -> None:
        """Create a manager. See the class docstring."""
        self._settings = settings
        self._steamcmd = steamcmd
        self._api = api
        self._history = history
        self._password = password
        self._redactor = redactor
        self._emit = emit
        self._guard_code_provider = guard_code_provider
        self._jobs: dict[int, DownloadJob] = {}
        self._game_names: dict[int, str] = {}
        self._login = SteamLogin()

    # ------------------------------------------------------------------ public

    def run(self, item_ids: Sequence[int], cancel: threading.Event) -> None:
        """Download the given item or collection IDs. Never raises."""
        self._jobs = {item_id: DownloadJob(item_id=item_id) for item_id in item_ids}
        try:
            self._run(list(item_ids), cancel)
        except SteamWDError as exc:
            logger.error("%s", exc)
            self._fail_unfinished(str(exc))
        except Exception as exc:
            logger.exception("Unexpected error during download")
            self._fail_unfinished(f"Unexpected error: {exc}")
        finally:
            if cancel.is_set():
                for job in self._jobs.values():
                    if not job.status.finished:
                        self._update(job, JobStatus.CANCELLED, "Stopped by user")
            self._emit(RunFinished(**self._counts()))

    # ---------------------------------------------------------------- pipeline

    def _run(self, root_ids: list[int], cancel: threading.Event) -> None:
        for job in self._jobs.values():
            self._update(job, JobStatus.RESOLVING, "Looking up item")
        item_jobs = self._expand_collections(root_ids)
        if cancel.is_set():
            return
        self._fill_details()
        if self._settings.skip_existing:
            self._skip_up_to_date(item_jobs)
        pending = [job for job in item_jobs if not job.status.finished]
        if not pending or cancel.is_set():
            return
        self._resolve_game_names(pending)
        self._ensure_steamcmd(pending, cancel)
        self._login = self._build_login()
        self._download_with_retries(pending, cancel)

    def _expand_collections(self, root_ids: list[int]) -> list[DownloadJob]:
        """Replace collections with their children. Returns the non-collection jobs in order."""
        item_jobs: list[DownloadJob] = []
        to_check = list(root_ids)
        checked: set[int] = set()
        while to_check:
            batch = [item_id for item_id in to_check if item_id not in checked]
            checked.update(batch)
            to_check = []
            if not batch:
                break
            collections = self._api.get_collection_children(batch)
            for item_id in batch:
                children = collections.get(item_id)
                job = self._jobs[item_id]
                if not children:
                    item_jobs.append(job)
                    continue
                job.is_collection = True
                added = 0
                for child_id, file_type in children:
                    if child_id in self._jobs:
                        continue
                    if file_type == COLLECTION_FILE_TYPE:
                        if not self._settings.expand_nested_collections:
                            continue
                        to_check.append(child_id)
                    child = DownloadJob(item_id=child_id, source_collection=item_id)
                    self._jobs[child_id] = child
                    self._update(child, JobStatus.RESOLVING, "Looking up item")
                    if file_type != COLLECTION_FILE_TYPE:
                        to_check.append(child_id)
                    added += 1
                self._update(job, JobStatus.DONE, f"Collection with {added} new item(s)")
        return item_jobs

    def _fill_details(self) -> None:
        items, errors = self._api.get_item_details(list(self._jobs))
        for item_id, job in self._jobs.items():
            item = items.get(item_id)
            if item:
                job.apply_item(item)
                if not job.is_collection:
                    self._update(job, JobStatus.QUEUED, "Waiting for steamcmd")
                else:
                    self._update(job, job.status, job.message)
            elif not job.is_collection:
                self._update(job, JobStatus.FAILED, errors.get(item_id, "Item not found"))

    def _skip_up_to_date(self, jobs: list[DownloadJob]) -> None:
        for job in jobs:
            if job.status.finished:
                continue
            entry = self._history.get(job.item_id)
            if entry and entry.time_updated >= job.time_updated and Path(entry.path).exists():
                job.output_path = Path(entry.path)
                self._update(job, JobStatus.SKIPPED, "Already downloaded and up to date")

    def _resolve_game_names(self, jobs: list[DownloadJob]) -> None:
        needs_names = self._settings.group_by == "game" or "{game}" in self._settings.naming_template
        if not needs_names:
            return
        for app_id in {job.app_id for job in jobs if job.app_id}:
            self._game_names[app_id] = self._api.get_app_name(app_id) or str(app_id)

    def _ensure_steamcmd(self, jobs: list[DownloadJob], cancel: threading.Event) -> None:
        if self._steamcmd.is_installed():
            return
        if not self._settings.auto_install_steamcmd:
            raise SteamCmdError(
                f"steamcmd was not found at {self._settings.steamcmd_path}. "
                "Set the path in Settings or enable automatic download."
            )
        for job in jobs:
            self._update(job, JobStatus.QUEUED, "Installing steamcmd")
        self._steamcmd.install(cancel, http_timeout=self._settings.api_timeout_seconds)

    def _build_login(self) -> SteamLogin:
        if self._settings.login_mode != "account":
            return SteamLogin()
        username = self._settings.username.strip()
        if not username:
            raise LoginError("Account login is enabled but no username is set in Settings.")
        self._redactor.add(self._password)
        return SteamLogin(username=username, password=self._password)

    def _download_with_retries(self, jobs: list[DownloadJob], cancel: threading.Event) -> None:
        remaining = jobs
        max_retries = self._settings.max_retries
        for attempt in range(max_retries + 1):
            if attempt:
                delay = self._settings.retry_delay_seconds
                for job in remaining:
                    self._update(job, JobStatus.QUEUED, f"Retry {attempt}/{max_retries} in {delay}s ({job.message})")
                if cancel.wait(delay):
                    return
            failed: list[DownloadJob] = []
            for batch in _chunked(remaining, self._settings.batch_size):
                if cancel.is_set():
                    return
                failed += self._download_batch(batch, cancel)
            remaining = failed
            if not remaining or cancel.is_set():
                return

    def _download_batch(self, batch: list[DownloadJob], cancel: threading.Event) -> list[DownloadJob]:
        """Download one batch. Returns jobs that failed and may be retried."""
        for job in batch:
            job.attempts += 1
            self._update(job, JobStatus.DOWNLOADING, f"Downloading (attempt {job.attempts})")
        outcome = self._run_steamcmd(batch, cancel)
        if cancel.is_set():
            return []

        results: dict[int, ItemDownloaded | ItemFailed] = {}
        for event in outcome.events:
            if isinstance(event, LoginFailed):
                raise LoginError(f"Steam login failed: {event.reason}")
            if isinstance(event, ItemDownloaded | ItemFailed):
                results[event.item_id] = event
            elif isinstance(event, DownloadProgress):
                progress_job = next((candidate for candidate in batch if candidate.item_id == event.item_id), None)
                if progress_job is not None:
                    progress_job.progress = event.percent
                    self._update(progress_job, JobStatus.DOWNLOADING, f"Downloading ({event.percent}%)")

        failed: list[DownloadJob] = []
        for job in batch:
            result = results.get(job.item_id)
            if isinstance(result, ItemDownloaded):
                if not self._place_files(job, result):
                    failed.append(job)
            elif isinstance(result, ItemFailed):
                self._update(job, JobStatus.FAILED, _describe_failure(result.reason))
                failed.append(job)
            elif outcome.timed_out:
                self._update(job, JobStatus.FAILED, "steamcmd timed out")
                failed.append(job)
            else:
                self._update(job, JobStatus.FAILED, "steamcmd did not report a result for this item")
                failed.append(job)
        return failed

    def _run_steamcmd(self, batch: list[DownloadJob], cancel: threading.Event) -> RunOutcome:
        items = [(job.app_id or 0, job.item_id) for job in batch]
        while True:
            args = self._steamcmd.build_download_args(
                install_dir=Path(self._settings.cache_dir),
                login=self._login,
                items=items,
                validate=self._settings.validate_downloads,
            )
            outcome = self._steamcmd.run(args, cancel)
            if outcome.password_required:
                raise LoginError("Steam asked for a password. Save your password in Settings > Steam account.")
            if not outcome.guard_required or cancel.is_set():
                # A guard code is single-use; later sessions rely on steamcmd's cached login.
                self._login = dataclasses.replace(self._login, guard_code=None)
                return outcome
            if not self._login.password:
                raise LoginError("Steam Guard code required, but no password is saved in Settings.")
            code = self._guard_code_provider(self._login.username or "")
            if not code:
                raise LoginError("Steam Guard code was not provided.")
            self._redactor.add(code)
            self._login = dataclasses.replace(self._login, guard_code=code.strip())

    def _place_files(self, job: DownloadJob, result: ItemDownloaded) -> bool:
        self._update(job, JobStatus.PROCESSING, "Moving files")
        app_id = job.app_id or 0
        source = Path(result.path)
        if not source.exists():
            source = (
                Path(self._settings.cache_dir) / "steamapps" / "workshop" / "content" / str(app_id) / str(job.item_id)
            )
        try:
            mode = self._settings.transfer_mode
            if mode == "leave":
                destination = source
            else:
                destination = files.transfer(source, self._destination(job), mode)
                if mode == "copy" and self._settings.clear_cache_after_copy:
                    files.remove_tree(source)
        except OSError as exc:
            self._update(job, JobStatus.FAILED, f"Downloaded, but could not place files: {exc}")
            return False
        job.output_path = destination
        self._history.record(
            item_id=job.item_id, title=job.title, app_id=app_id, time_updated=job.time_updated, path=destination
        )
        self._update(job, JobStatus.DONE, str(destination))
        return True

    def _destination(self, job: DownloadJob) -> Path:
        app_id = job.app_id or 0
        game = self._game_names.get(app_id, str(app_id))
        base = Path(self._settings.output_dir)
        if self._settings.group_by == "appid":
            base /= str(app_id)
        elif self._settings.group_by == "game":
            base /= sanitize_filename(game) or str(app_id)
        name = render_folder_name(
            self._settings.naming_template, item_id=job.item_id, title=job.title, app_id=app_id, game=game
        )
        destination = base / name
        owner = self._history.owner_of(destination)
        if destination.exists() and owner != job.item_id:
            destination = base / f"{name} ({job.item_id})"
        return destination

    # ----------------------------------------------------------------- helpers

    def _update(self, job: DownloadJob, status: JobStatus, message: str) -> None:
        job.status = status
        job.message = message
        self._emit(JobChanged(dataclasses.replace(job)))

    def _fail_unfinished(self, message: str) -> None:
        for job in self._jobs.values():
            if not job.status.finished:
                self._update(job, JobStatus.FAILED, message)

    def _counts(self) -> dict[str, int]:
        counts = {"done": 0, "skipped": 0, "failed": 0, "cancelled": 0}
        for job in self._jobs.values():
            if job.is_collection:
                continue
            key = {
                JobStatus.DONE: "done",
                JobStatus.SKIPPED: "skipped",
                JobStatus.FAILED: "failed",
                JobStatus.CANCELLED: "cancelled",
            }.get(job.status)
            if key:
                counts[key] += 1
        return counts


def _chunked(jobs: list[DownloadJob], size: int) -> Iterator[list[DownloadJob]]:
    for start in range(0, len(jobs), max(1, size)):
        yield jobs[start : start + size]


def _describe_failure(reason: str) -> str:
    hint = _FAILURE_HINTS.get(reason.strip().lower())
    return f"steamcmd: {reason} ({hint})" if hint else f"steamcmd: {reason}"
