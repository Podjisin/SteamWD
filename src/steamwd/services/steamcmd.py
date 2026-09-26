"""Run steamcmd.exe and stream its output as structured events."""

import codecs
import contextlib
import logging
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import requests

from steamwd.core.steamcmd_output import (
    GuardCodeRequested,
    OutputEvent,
    PasswordRequested,
    is_guard_prompt,
    is_password_prompt,
    parse_line,
)
from steamwd.errors import SteamCmdError

__all__ = ["STEAMCMD_ZIP_URL", "RunOutcome", "SteamCmd", "SteamLogin", "find_steamcmd"]

logger = logging.getLogger(__name__)
output_logger = logging.getLogger("steamwd.steamcmd.output")

STEAMCMD_ZIP_URL = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"
_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_EXE_NAME = "steamcmd.exe"
_COMMON_LOCATIONS = (Path("C:/steamcmd"), Path("C:/SteamCMD"), Path("C:/Program Files/steamcmd"))


def find_steamcmd(extra_dirs: Sequence[Path] = ()) -> Path | None:
    """Look for an existing ``steamcmd.exe`` so it doesn't have to be downloaded again.

    Searches, in order: ``extra_dirs``, the folder of the running program (next to
    ``SteamWD.exe`` when frozen), the current folder, ``PATH`` and common install folders.
    """
    candidates = [*extra_dirs]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent)
    candidates.append(Path.cwd())
    for directory in candidates:
        exe = directory / _EXE_NAME
        if exe.is_file():
            return exe.resolve()
    on_path = shutil.which("steamcmd")
    if on_path:
        return Path(on_path).resolve()
    for directory in _COMMON_LOCATIONS:
        exe = directory / _EXE_NAME
        if exe.is_file():
            return exe.resolve()
    return None


@dataclass(frozen=True, slots=True)
class SteamLogin:
    """Credentials for a steamcmd session. ``username=None`` means anonymous."""

    username: str | None = None
    password: str | None = None
    guard_code: str | None = None

    def args(self) -> list[str]:
        """Arguments for the ``+login`` command."""
        if not self.username:
            return ["+login", "anonymous"]
        args = ["+login", self.username]
        if self.password:
            args.append(self.password)
            if self.guard_code:
                args.append(self.guard_code)
        return args


@dataclass(slots=True)
class RunOutcome:
    """Result of one steamcmd process run."""

    exit_code: int | None = None
    events: list[OutputEvent] = field(default_factory=list)
    guard_required: bool = False
    password_required: bool = False
    cancelled: bool = False
    timed_out: bool = False


class SteamCmd:
    """Wrapper around a ``steamcmd.exe`` installation."""

    def __init__(self, exe_path: Path, timeout_seconds: float) -> None:
        """Create a wrapper.

        Args:
            exe_path: Location of ``steamcmd.exe`` (may not exist yet).
            timeout_seconds: Maximum runtime of a single steamcmd process.
        """
        self.exe_path = exe_path
        self.timeout_seconds = timeout_seconds

    def is_installed(self) -> bool:
        """Whether ``steamcmd.exe`` exists."""
        return self.exe_path.is_file()

    def install(self, cancel: threading.Event, http_timeout: float = 60) -> None:
        """Download and bootstrap steamcmd into ``exe_path``'s folder."""
        target_dir = self.exe_path.parent
        logger.info("Installing steamcmd into %s", target_dir)
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            archive = target_dir / "steamcmd.zip"
            with requests.get(STEAMCMD_ZIP_URL, stream=True, timeout=http_timeout) as response:
                response.raise_for_status()
                with archive.open("wb") as handle:
                    shutil.copyfileobj(response.raw, handle)
            with zipfile.ZipFile(archive) as zipped:
                zipped.extractall(target_dir)
            archive.unlink(missing_ok=True)
        except (OSError, requests.RequestException, zipfile.BadZipFile) as exc:
            raise SteamCmdError(f"Could not download steamcmd: {exc}") from exc
        if self.exe_path.name.lower() != "steamcmd.exe":
            extracted = target_dir / "steamcmd.exe"
            if extracted.is_file() and not self.exe_path.exists():
                extracted.rename(self.exe_path)
        if not self.is_installed():
            raise SteamCmdError(f"steamcmd.exe was not found in the downloaded archive ({target_dir})")
        logger.info("Updating steamcmd (first run can take a few minutes)")
        self.run([str(self.exe_path), "+quit"], cancel)

    def build_download_args(
        self, *, install_dir: Path, login: SteamLogin, items: Sequence[tuple[int, int]], validate: bool
    ) -> list[str]:
        """Build the argument list for downloading ``(app_id, item_id)`` pairs."""
        args = [str(self.exe_path), "+force_install_dir", str(install_dir), *login.args()]
        for app_id, item_id in items:
            args += ["+workshop_download_item", str(app_id), str(item_id)]
            if validate:
                args.append("validate")
        args.append("+quit")
        return args

    def run(self, args: Sequence[str], cancel: threading.Event) -> RunOutcome:
        """Run steamcmd, parsing output until it exits, is cancelled or times out.

        Interactive prompts (password, Steam Guard) stop the process and are
        reported in the outcome so the caller can retry with more information.
        """
        logger.info("Starting steamcmd: %s", " ".join(args[1:]))
        try:
            process = subprocess.Popen(
                list(args),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
                cwd=self.exe_path.parent,
                creationflags=_CREATE_NO_WINDOW,
            )
        except OSError as exc:
            raise SteamCmdError(f"Could not start {self.exe_path}: {exc}") from exc

        outcome = RunOutcome()
        watchdog = threading.Thread(target=self._watch, args=(process, cancel, outcome), daemon=True)
        watchdog.start()
        self._read_output(process, outcome)
        outcome.exit_code = process.wait()
        watchdog.join(timeout=2)
        logger.info("steamcmd exited with code %s", outcome.exit_code)
        return outcome

    def _watch(self, process: "subprocess.Popen[bytes]", cancel: threading.Event, outcome: RunOutcome) -> None:
        deadline = time.monotonic() + self.timeout_seconds
        while process.poll() is None:
            if cancel.is_set():
                outcome.cancelled = True
                _kill(process)
                return
            if time.monotonic() > deadline:
                outcome.timed_out = True
                logger.warning("steamcmd timed out after %.0f seconds", self.timeout_seconds)
                _kill(process)
                return
            time.sleep(0.25)

    def _read_output(self, process: "subprocess.Popen[bytes]", outcome: RunOutcome) -> None:
        assert process.stdout is not None
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        buffer = ""
        while chunk := process.stdout.read(4096):
            buffer += decoder.decode(chunk)
            *lines, buffer = _LINE_BREAK.split(buffer)
            for line in lines:
                self._handle_line(line, process, outcome)
            if is_guard_prompt(buffer) or is_password_prompt(buffer):
                self._handle_line(buffer, process, outcome)
                buffer = ""
        buffer += decoder.decode(b"", final=True)
        if buffer.strip():
            self._handle_line(buffer, process, outcome)

    @staticmethod
    def _handle_line(line: str, process: "subprocess.Popen[bytes]", outcome: RunOutcome) -> None:
        text = line.strip()
        if not text:
            return
        output_logger.info("%s", text)
        event = parse_line(text)
        if event is None:
            return
        if isinstance(event, GuardCodeRequested):
            outcome.guard_required = True
            _kill(process)
        elif isinstance(event, PasswordRequested):
            outcome.password_required = True
            _kill(process)
        else:
            outcome.events.append(event)


def _kill(process: "subprocess.Popen[bytes]") -> None:
    with contextlib.suppress(OSError):
        process.kill()
