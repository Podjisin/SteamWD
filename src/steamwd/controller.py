import dataclasses
import logging
import queue
import threading
import tkinter as tk
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import messagebox, simpledialog

from steamwd.config import paths
from steamwd.config.settings import Settings
from steamwd.config.store import SettingsStore, export_settings, import_settings
from steamwd.core.models import DownloadJob, JobStatus, workshop_url
from steamwd.core.parsing import parse_workshop_ids
from steamwd.errors import CredentialError, SettingsError
from steamwd.gui.main_window import MainWindow
from steamwd.logging_setup import QueueTextHandler, Redactor, configure_logging
from steamwd.services import files
from steamwd.services.credentials import CredentialStore
from steamwd.services.downloader import DownloadEvent, DownloadManager, JobChanged, RunFinished
from steamwd.services.history import DownloadHistory
from steamwd.services.steam_api import SteamApi
from steamwd.services.steamcmd import SteamCmd, find_steamcmd

__all__ = ["Controller"]

logger = logging.getLogger(__name__)
_POLL_MS = 100
_MAX_MESSAGES_PER_POLL = 500


@dataclass(frozen=True, slots=True)
class _LogLine:
    text: str


@dataclass(slots=True)
class _GuardCodeRequest:
    username: str
    done: threading.Event = field(default_factory=threading.Event)
    code: str | None = None


_UiMessage = DownloadEvent | _LogLine | _GuardCodeRequest


class Controller:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._messages: queue.Queue[object] = queue.Queue()
        self._redactor = Redactor()
        self._gui_log_handler = QueueTextHandler(self._messages, _LogLine)
        self._store = SettingsStore(paths.settings_file())
        self.settings, warnings = self._store.load()
        self._configure_logging()
        self._credentials = CredentialStore()
        self._history = DownloadHistory(paths.history_file())
        self._jobs: dict[int, DownloadJob] = {}
        self._worker: threading.Thread | None = None
        self._cancel = threading.Event()
        self._stop_requested = False
        self._run_ids: set[int] = set()

        self.window = MainWindow(root, self)
        self.window.apply_theme(self.settings.theme)
        self._refresh_summary()
        logger.info("SteamWD started. Settings: %s", self._store.path)
        for warning in warnings:
            logger.warning("Settings: %s", warning)
        if warnings:
            messagebox.showwarning("Settings", "Some settings were invalid and reset:\n\n" + "\n".join(warnings))
        root.after(_POLL_MS, self._poll)

    # ------------------------------------------------------------------ queue

    @property
    def running(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def add_inputs(self, text: str) -> tuple[int, list[str]]:
        result = parse_workshop_ids(text)
        added = 0
        for item_id in result.ids:
            existing = self._jobs.get(item_id)
            if existing and not existing.status.finished:
                continue
            job = DownloadJob(item_id=item_id)
            if existing:
                job.title, job.app_id, job.file_size = existing.title, existing.app_id, existing.file_size
                job.source_collection = existing.source_collection
            self._jobs[item_id] = job
            self.window.downloads.upsert_job(job)
            added += 1
        if added:
            logger.info("Added %d item(s) to the queue", added)
        self._refresh_summary()
        return added, result.invalid

    def start(self) -> None:
        if self.running:
            return
        ids = [job.item_id for job in self._jobs.values() if job.status is JobStatus.QUEUED]
        if not ids:
            self._refresh_summary("Nothing queued. Add links above, or use Retry failed.")
            return
        if self.settings.login_mode == "account" and not self.settings.username.strip():
            messagebox.showerror("Steam account", "Account login is enabled, but no username is set in Settings.")
            return
        password = self._saved_password(self.settings.username) if self.settings.login_mode == "account" else None
        self._locate_existing_steamcmd()
        self._history.load()
        self._run_ids = set(ids)
        self._cancel = threading.Event()
        self._stop_requested = False
        manager = DownloadManager(
            settings=self.settings,
            steamcmd=SteamCmd(Path(self.settings.steamcmd_path), self.settings.steamcmd_timeout_minutes * 60),
            api=SteamApi(timeout=self.settings.api_timeout_seconds),
            history=self._history,
            password=password,
            redactor=self._redactor,
            emit=self._messages.put,
            guard_code_provider=self._ask_guard_code,
        )
        self._worker = threading.Thread(
            target=manager.run, args=(ids, self._cancel), name="steamwd-download", daemon=True
        )
        self._worker.start()
        self.window.downloads.set_running(True)
        logger.info("Starting download of %d item(s)", len(ids))

    def stop(self) -> None:
        """Cancel the current run."""
        if self.running:
            self._stop_requested = True
            self._cancel.set()
            logger.info("Stopping...")
            self._refresh_summary("Stopping...")

    def retry_failed(self) -> None:
        """Requeue failed and cancelled items and start."""
        if self.running:
            return
        for job in self._jobs.values():
            if job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
                job.status, job.message, job.attempts = JobStatus.QUEUED, "", 0
                self.window.downloads.upsert_job(job)
        self.start()

    def remove_jobs(self, item_ids: list[int]) -> None:
        """Remove rows that are not being processed, including their children."""
        removed: list[int] = []
        for root_id in item_ids:
            if root_id not in self._jobs:
                continue
            group = {root_id} | self._descendants(root_id)
            if any(self._jobs[i].status.active for i in group) or (self.running and group & self._run_ids):
                continue
            for item_id in group:
                self._jobs.pop(item_id, None)
            removed.append(root_id)
        self.window.downloads.remove_rows(removed)
        self._refresh_summary()

    def _descendants(self, item_id: int) -> set[int]:
        found: set[int] = set()
        frontier = {item_id}
        while frontier:
            frontier = {j.item_id for j in self._jobs.values() if j.source_collection in frontier} - found
            found |= frontier
        return found

    def clear_finished(self) -> None:
        """Remove done and skipped rows (collections only when all their items are finished too)."""

        def clearable(job: DownloadJob) -> bool:
            if job.status not in (JobStatus.DONE, JobStatus.SKIPPED):
                return False
            children = [j for j in self._jobs.values() if j.source_collection == job.item_id]
            return all(clearable(child) for child in children)

        self.remove_jobs([job.item_id for job in list(self._jobs.values()) if clearable(job)])

    def open_job(self, item_id: int) -> None:
        """Open a job's output folder, or its Workshop page if it has not been downloaded."""
        job = self._jobs.get(item_id)
        if job and job.output_path and job.output_path.exists():
            files.open_in_explorer(job.output_path)
        else:
            webbrowser.open(workshop_url(item_id))

    def open_output_folder(self) -> None:
        """Open the configured output folder."""
        self._open_folder(Path(self.settings.output_dir))

    def open_log_folder(self) -> None:
        """Open the log folder."""
        self._open_folder(Path(self.settings.log_dir))

    def open_settings_folder(self) -> None:
        """Open the folder containing settings.json."""
        self._open_folder(self._store.path.parent)

    # --------------------------------------------------------------- settings

    def save_settings(self, settings: Settings) -> bool:
        """Persist and apply new settings."""
        try:
            self._store.save(settings)
        except SettingsError as exc:
            messagebox.showerror("Settings", str(exc))
            return False
        self.settings = settings
        self._configure_logging()
        self.window.apply_theme(settings.theme)
        logger.info("Settings saved")
        if self.running:
            logger.info("The current run keeps its old settings; new settings apply to the next run.")
        return True

    def import_settings(self, path: Path) -> tuple[Settings, list[str]] | None:
        """Read settings from a file for the form (not saved yet)."""
        try:
            return import_settings(path)
        except SettingsError as exc:
            messagebox.showerror("Import settings", str(exc))
            return None

    def export_settings(self, path: Path) -> None:
        """Export the saved settings (never includes passwords)."""
        try:
            export_settings(path, self.settings)
            messagebox.showinfo("Export settings", f"Settings exported to {path}.\nPasswords are not included.")
        except SettingsError as exc:
            messagebox.showerror("Export settings", str(exc))

    def save_password(self, username: str, password: str) -> bool:
        """Save a password in Windows Credential Manager."""
        try:
            self._credentials.set_password(username, password)
        except CredentialError as exc:
            messagebox.showerror("Password", str(exc))
            return False
        self._redactor.add(password)
        logger.info("Password for %s saved in Windows Credential Manager", username)
        return True

    def delete_password(self, username: str) -> bool:
        """Delete a saved password."""
        try:
            self._credentials.delete_password(username)
        except CredentialError as exc:
            messagebox.showerror("Password", str(exc))
            return False
        logger.info("Saved password for %s removed", username)
        return True

    def has_password(self, username: str) -> bool:
        """Whether a password is saved for ``username``."""
        try:
            return bool(self._credentials.get_password(username))
        except CredentialError:
            return False

    # -------------------------------------------------------------- lifecycle

    def on_close(self) -> None:
        """Handle the window close button."""
        if self.running:
            if self.settings.confirm_exit_while_running and not messagebox.askyesno(
                "Downloads running", "Downloads are still running. Stop them and exit?"
            ):
                return
            self._cancel.set()
            if self._worker:
                self._worker.join(timeout=5)
        self.root.destroy()

    # --------------------------------------------------------------- internal

    def _poll(self) -> None:
        try:
            for _ in range(_MAX_MESSAGES_PER_POLL):
                self._handle(self._messages.get_nowait())
        except queue.Empty:
            pass
        finally:
            self.root.after(_POLL_MS, self._poll)

    def _handle(self, message: object) -> None:
        if isinstance(message, _LogLine):
            self.window.log.append(message.text)
        elif isinstance(message, JobChanged):
            self._run_ids.add(message.job.item_id)
            self._jobs[message.job.item_id] = message.job
            self.window.downloads.upsert_job(message.job)
            self._refresh_summary()
        elif isinstance(message, RunFinished):
            self._on_run_finished(message)
        elif isinstance(message, _GuardCodeRequest):
            message.code = simpledialog.askstring(
                "Steam Guard",
                f"Enter the Steam Guard code for '{message.username}'\n(from the Steam mobile app or your email):",
                parent=self.root,
            )
            message.done.set()

    def _on_run_finished(self, result: RunFinished) -> None:
        if self._worker:
            self._worker.join(timeout=1)
        self.window.downloads.set_running(False)
        summary = (
            f"Finished: {result.done} downloaded, {result.skipped} skipped, "
            f"{result.failed} failed, {result.cancelled} cancelled"
        )
        logger.info("%s", summary)
        self._refresh_summary(summary)
        if result.done and self.settings.open_output_when_done:
            self.open_output_folder()
        if not self._stop_requested and any(j.status is JobStatus.QUEUED for j in self._jobs.values()):
            self.start()

    def _locate_existing_steamcmd(self) -> None:
        """If the configured steamcmd is missing, reuse an existing install instead of downloading one."""
        if Path(self.settings.steamcmd_path).is_file():
            return
        found = find_steamcmd()
        if found is None:
            return
        logger.info("steamcmd not found at %s; using existing %s", self.settings.steamcmd_path, found)
        updated = dataclasses.replace(self.settings, steamcmd_path=str(found))
        try:
            self._store.save(updated)
        except SettingsError as exc:
            logger.warning("%s", exc)
        self.settings = updated
        self.window.settings.load(updated)

    def _ask_guard_code(self, username: str) -> str | None:
        request = _GuardCodeRequest(username=username)
        self._messages.put(request)
        while not request.done.wait(0.2):
            if self._cancel.is_set():
                return None
        return request.code

    def _saved_password(self, username: str) -> str | None:
        try:
            password = self._credentials.get_password(username)
        except CredentialError as exc:
            logger.warning("%s", exc)
            return None
        self._redactor.add(password)
        return password

    def _configure_logging(self) -> None:
        self._gui_log_handler.setLevel(self.settings.log_level)
        configure_logging(Path(self.settings.log_dir), self.settings.log_level, self._redactor, [self._gui_log_handler])

    def _refresh_summary(self, text: str | None = None) -> None:
        items = [j for j in self._jobs.values() if not j.is_collection]
        finished = sum(1 for j in items if j.status.finished)
        if text is None:
            if not items:
                text = "Queue is empty"
            else:
                failed = sum(1 for j in items if j.status is JobStatus.FAILED)
                text = f"{finished}/{len(items)} finished" + (f", {failed} failed" if failed else "")
        self.window.downloads.set_summary(len(items), finished, text)

    def _open_folder(self, path: Path) -> None:
        try:
            files.open_in_explorer(path)
        except OSError as exc:
            messagebox.showerror("Open folder", f"Could not open {path}: {exc}")
