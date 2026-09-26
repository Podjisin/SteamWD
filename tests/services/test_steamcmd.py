import sys
import threading
from pathlib import Path

import pytest

from steamwd.core.steamcmd_output import ItemDownloaded, ItemFailed
from steamwd.services.steamcmd import SteamCmd, SteamLogin, find_steamcmd


def test_find_steamcmd_prefers_given_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("shutil.which", lambda _name: None)
    monkeypatch.setattr("steamwd.services.steamcmd._COMMON_LOCATIONS", ())
    assert find_steamcmd() is None
    (tmp_path / "steamcmd.exe").write_bytes(b"")
    assert find_steamcmd() == (tmp_path / "steamcmd.exe").resolve()
    other = tmp_path / "other"
    other.mkdir()
    (other / "steamcmd.exe").write_bytes(b"")
    assert find_steamcmd([other]) == (other / "steamcmd.exe").resolve()


def test_login_args() -> None:
    assert SteamLogin().args() == ["+login", "anonymous"]
    assert SteamLogin("bob").args() == ["+login", "bob"]
    assert SteamLogin("bob", "pw", "CODE1").args() == ["+login", "bob", "pw", "CODE1"]
    assert SteamLogin("bob", None, "CODE1").args() == ["+login", "bob"]


def test_build_download_args() -> None:
    cmd = SteamCmd(Path("C:/steamcmd/steamcmd.exe"), 60)
    args = cmd.build_download_args(
        install_dir=Path("C:/cache"), login=SteamLogin(), items=[(4000, 1), (294100, 2)], validate=True
    )
    assert args[1:] == [
        "+force_install_dir",
        str(Path("C:/cache")),
        "+login",
        "anonymous",
        "+workshop_download_item",
        "4000",
        "1",
        "validate",
        "+workshop_download_item",
        "294100",
        "2",
        "validate",
        "+quit",
    ]


def _fake(script: str, timeout: float = 30) -> tuple[SteamCmd, list[str]]:
    return SteamCmd(Path(sys.executable), timeout), [sys.executable, "-c", script]


def test_run_parses_output() -> None:
    cmd, args = _fake(
        "print('Loading...');"
        "print('Success. Downloaded item 1 to \"C:\\\\x\\\\1\" (10 bytes)');"
        "print('ERROR! Download item 2 failed (Failure).')"
    )
    outcome = cmd.run(args, threading.Event())
    assert outcome.exit_code == 0
    assert outcome.events == [ItemDownloaded(1, "C:\\x\\1", 10), ItemFailed(2, "Failure")]


def test_run_detects_guard_prompt_without_newline() -> None:
    cmd, args = _fake("import sys, time; sys.stdout.write('Steam Guard code:'); sys.stdout.flush(); time.sleep(30)")
    outcome = cmd.run(args, threading.Event())
    assert outcome.guard_required


def test_run_times_out() -> None:
    cmd, args = _fake("import time; time.sleep(30)", timeout=0.5)
    outcome = cmd.run(args, threading.Event())
    assert outcome.timed_out


def test_run_can_be_cancelled() -> None:
    cmd, args = _fake("import time; time.sleep(30)")
    cancel = threading.Event()
    threading.Timer(0.3, cancel.set).start()
    outcome = cmd.run(args, cancel)
    assert outcome.cancelled
