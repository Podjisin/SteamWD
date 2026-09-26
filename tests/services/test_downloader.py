import threading
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from steamwd.config.settings import Settings
from steamwd.core.models import JobStatus, WorkshopItem
from steamwd.core.steamcmd_output import DownloadProgress, ItemDownloaded, ItemFailed, LoginFailed, OutputEvent
from steamwd.logging_setup import Redactor
from steamwd.services.downloader import DownloadEvent, DownloadManager, JobChanged, RunFinished
from steamwd.services.history import DownloadHistory
from steamwd.services.steamcmd import RunOutcome, SteamLogin


class FakeApi:
    def __init__(self, items: dict[int, WorkshopItem], collections: dict[int, list[tuple[int, int]]] | None = None):
        self.items = items
        self.collections = collections or {}

    def get_item_details(self, item_ids: Sequence[int]) -> tuple[dict[int, WorkshopItem], dict[int, str]]:
        found = {i: self.items[i] for i in item_ids if i in self.items}
        return found, {i: "Item not found" for i in item_ids if i not in self.items}

    def get_collection_children(self, item_ids: Sequence[int]) -> dict[int, list[tuple[int, int]]]:
        return {i: self.collections[i] for i in item_ids if i in self.collections}

    def get_app_name(self, app_id: int) -> str | None:
        return f"Game {app_id}"


Behaviour = Callable[[SteamLogin, list[tuple[int, int]]], RunOutcome]


class FakeSteamCmd:
    """Creates item folders in the cache like steamcmd would."""

    def __init__(self, cache: Path, behaviour: Behaviour | None = None) -> None:
        self.cache = cache
        self.behaviour = behaviour
        self.calls: list[tuple[SteamLogin, list[tuple[int, int]]]] = []
        self._pending: tuple[SteamLogin, list[tuple[int, int]]] | None = None
        self.installed = True

    def is_installed(self) -> bool:
        return self.installed

    def install(self, cancel: threading.Event, http_timeout: float = 60) -> None:
        self.installed = True

    def build_download_args(
        self, *, install_dir: Path, login: SteamLogin, items: Sequence[tuple[int, int]], validate: bool
    ) -> list[str]:
        self._pending = (login, list(items))
        return ["steamcmd"]

    def run(self, args: Sequence[str], cancel: threading.Event) -> RunOutcome:
        assert self._pending
        login, items = self._pending
        self.calls.append((login, items))
        if self.behaviour:
            return self.behaviour(login, items)
        return RunOutcome(exit_code=0, events=[self.download(app, item) for app, item in items])

    def download(self, app_id: int, item_id: int) -> ItemDownloaded:
        folder = self.cache / "steamapps" / "workshop" / "content" / str(app_id) / str(item_id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "mod.txt").write_text(str(item_id), encoding="utf-8")
        return ItemDownloaded(item_id, str(folder), 1)


def _item(item_id: int, title: str = "", app_id: int = 4000, updated: int = 1) -> WorkshopItem:
    return WorkshopItem(item_id=item_id, title=title or f"Item {item_id}", app_id=app_id, time_updated=updated)


class Harness:
    def __init__(self, tmp_path: Path, **overrides: object) -> None:
        self.settings = Settings(
            cache_dir=str(tmp_path / "cache"),
            output_dir=str(tmp_path / "out"),
            retry_delay_seconds=0,
            **overrides,  # type: ignore[arg-type]
        )
        self.history = DownloadHistory(tmp_path / "history.json")
        self.events: list[DownloadEvent] = []
        self.guard_codes: list[str | None] = []

    def run(
        self, ids: list[int], api: FakeApi, steamcmd: FakeSteamCmd, password: str | None = None
    ) -> dict[int, JobChanged]:
        manager = DownloadManager(
            settings=self.settings,
            steamcmd=steamcmd,
            api=api,
            history=self.history,
            password=password,
            redactor=Redactor(),
            emit=self.events.append,
            guard_code_provider=lambda _user: self.guard_codes.pop(0) if self.guard_codes else None,
        )
        manager.run(ids, threading.Event())
        latest: dict[int, JobChanged] = {}
        for event in self.events:
            if isinstance(event, JobChanged):
                latest[event.job.item_id] = event
        return latest

    @property
    def finished(self) -> RunFinished:
        last = self.events[-1]
        assert isinstance(last, RunFinished)
        return last


def test_downloads_and_copies_to_output(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    steamcmd = FakeSteamCmd(tmp_path / "cache")
    jobs = h.run([1, 2], FakeApi({1: _item(1, "Cool Map"), 2: _item(2)}), steamcmd)

    assert jobs[1].job.status is JobStatus.DONE
    assert (tmp_path / "out" / "Cool Map" / "mod.txt").read_text(encoding="utf-8") == "1"
    assert not (tmp_path / "cache" / "steamapps" / "workshop" / "content" / "4000" / "1").exists()
    assert h.finished == RunFinished(done=2, skipped=0, failed=0, cancelled=0)
    assert steamcmd.calls[0][0] == SteamLogin()


def test_progress_events_update_the_job(tmp_path: Path) -> None:
    h = Harness(tmp_path)

    def progressing(_login: SteamLogin, items: list[tuple[int, int]]) -> RunOutcome:
        app_id, item_id = items[0]
        steamcmd.download(app_id, item_id)
        return RunOutcome(
            events=[
                DownloadProgress(item_id, 42),
                ItemDownloaded(
                    item_id,
                    str(tmp_path / "cache" / "steamapps" / "workshop" / "content" / str(app_id) / str(item_id)),
                    1,
                ),
            ]
        )

    steamcmd = FakeSteamCmd(tmp_path / "cache", progressing)
    jobs = h.run([1], FakeApi({1: _item(1)}), steamcmd)
    assert jobs[1].job.status is JobStatus.DONE
    progress_events = [event for event in h.events if isinstance(event, JobChanged) and event.job.progress == 42]
    assert progress_events


def test_collection_is_expanded_with_nested_collections(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    api = FakeApi(
        {100: _item(100, "Pack"), 101: _item(101, "Sub"), 1: _item(1), 2: _item(2), 3: _item(3)},
        {100: [(1, 0), (101, 2), (2, 0)], 101: [(3, 0), (1, 0)]},
    )
    jobs = h.run([100], api, FakeSteamCmd(tmp_path / "cache"))

    assert jobs[100].job.is_collection
    assert jobs[101].job.is_collection
    assert {i for i, e in jobs.items() if e.job.status is JobStatus.DONE and not e.job.is_collection} == {1, 2, 3}
    assert jobs[3].job.source_collection == 101
    assert h.finished.done == 3


def test_nested_collections_can_be_disabled(tmp_path: Path) -> None:
    h = Harness(tmp_path, expand_nested_collections=False)
    api = FakeApi({100: _item(100), 101: _item(101), 1: _item(1), 3: _item(3)}, {100: [(1, 0), (101, 2)]})
    jobs = h.run([100], api, FakeSteamCmd(tmp_path / "cache"))
    assert set(jobs) == {100, 1}


def test_failed_items_are_retried(tmp_path: Path) -> None:
    h = Harness(tmp_path, max_retries=2)
    attempts: list[int] = []

    def flaky(login: SteamLogin, items: list[tuple[int, int]]) -> RunOutcome:
        attempts.append(len(items))
        events: list[OutputEvent] = []
        for app, item in items:
            if item == 2 and len(attempts) < 3:
                events.append(ItemFailed(item, "Timeout"))
            else:
                events.append(steamcmd.download(app, item))
        return RunOutcome(exit_code=0, events=events)

    steamcmd = FakeSteamCmd(tmp_path / "cache", flaky)
    jobs = h.run([1, 2], FakeApi({1: _item(1), 2: _item(2)}), steamcmd)
    assert attempts == [2, 1, 1]
    assert jobs[2].job.status is JobStatus.DONE
    assert jobs[2].job.attempts == 3


def test_gives_up_after_max_retries(tmp_path: Path) -> None:
    h = Harness(tmp_path, max_retries=1)
    steamcmd = FakeSteamCmd(
        tmp_path / "cache", lambda _l, items: RunOutcome(events=[ItemFailed(i, "Failure") for _, i in items])
    )
    jobs = h.run([1], FakeApi({1: _item(1)}), steamcmd)
    assert jobs[1].job.status is JobStatus.FAILED
    assert "owns it" in jobs[1].job.message
    assert len(steamcmd.calls) == 2


def test_unknown_items_fail_without_calling_steamcmd(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    steamcmd = FakeSteamCmd(tmp_path / "cache")
    jobs = h.run([9], FakeApi({}), steamcmd)
    assert jobs[9].job.status is JobStatus.FAILED
    assert steamcmd.calls == []


def test_up_to_date_items_are_skipped(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    api = FakeApi({1: _item(1, updated=5)})
    h.run([1], api, FakeSteamCmd(tmp_path / "cache"))
    h.events.clear()
    steamcmd = FakeSteamCmd(tmp_path / "cache")
    jobs = h.run([1], api, steamcmd)
    assert jobs[1].job.status is JobStatus.SKIPPED
    assert steamcmd.calls == []

    h.events.clear()
    jobs = h.run([1], FakeApi({1: _item(1, updated=6)}), steamcmd)
    assert jobs[1].job.status is JobStatus.DONE


def test_grouping_and_naming(tmp_path: Path) -> None:
    h = Harness(tmp_path, group_by="game", naming_template="{id} - {title}")
    h.run([1], FakeApi({1: _item(1, "Map", app_id=4000)}), FakeSteamCmd(tmp_path / "cache"))
    assert (tmp_path / "out" / "Game 4000" / "1 - Map" / "mod.txt").exists()


def test_title_collision_gets_id_suffix(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    h.run([1, 2], FakeApi({1: _item(1, "Same"), 2: _item(2, "Same")}), FakeSteamCmd(tmp_path / "cache"))
    assert (tmp_path / "out" / "Same").exists()
    assert (tmp_path / "out" / "Same (2)").exists()


def test_leave_mode_keeps_files_in_cache(tmp_path: Path) -> None:
    h = Harness(tmp_path, transfer_mode="leave")
    jobs = h.run([1], FakeApi({1: _item(1)}), FakeSteamCmd(tmp_path / "cache"))
    assert jobs[1].job.output_path == tmp_path / "cache" / "steamapps" / "workshop" / "content" / "4000" / "1"
    assert not (tmp_path / "out").exists()


def test_login_failure_fails_all_items(tmp_path: Path) -> None:
    h = Harness(tmp_path, login_mode="account", username="bob")
    steamcmd = FakeSteamCmd(tmp_path / "cache", lambda _l, _i: RunOutcome(events=[LoginFailed("Invalid Password")]))
    jobs = h.run([1, 2], FakeApi({1: _item(1), 2: _item(2)}), steamcmd, password="pw123")
    assert all(e.job.status is JobStatus.FAILED for e in jobs.values())
    assert "Invalid Password" in jobs[1].job.message
    assert len(steamcmd.calls) == 1
    assert steamcmd.calls[0][0] == SteamLogin("bob", "pw123")


def test_steam_guard_code_is_requested_and_used(tmp_path: Path) -> None:
    h = Harness(tmp_path, login_mode="account", username="bob")
    h.guard_codes = ["ABCDE"]

    def guarded(login: SteamLogin, items: list[tuple[int, int]]) -> RunOutcome:
        if not login.guard_code:
            return RunOutcome(guard_required=True)
        return RunOutcome(events=[steamcmd.download(a, i) for a, i in items])

    steamcmd = FakeSteamCmd(tmp_path / "cache", guarded)
    jobs = h.run([1], FakeApi({1: _item(1)}), steamcmd, password="pw123")
    assert jobs[1].job.status is JobStatus.DONE
    assert [c[0].guard_code for c in steamcmd.calls] == [None, "ABCDE"]


def test_missing_guard_code_fails(tmp_path: Path) -> None:
    h = Harness(tmp_path, login_mode="account", username="bob")
    steamcmd = FakeSteamCmd(tmp_path / "cache", lambda _l, _i: RunOutcome(guard_required=True))
    jobs = h.run([1], FakeApi({1: _item(1)}), steamcmd, password="pw123")
    assert jobs[1].job.status is JobStatus.FAILED
    assert "Steam Guard" in jobs[1].job.message


def test_account_mode_without_username_fails(tmp_path: Path) -> None:
    h = Harness(tmp_path, login_mode="account")
    jobs = h.run([1], FakeApi({1: _item(1)}), FakeSteamCmd(tmp_path / "cache"))
    assert "username" in jobs[1].job.message


def test_batches_respect_batch_size(tmp_path: Path) -> None:
    h = Harness(tmp_path, batch_size=2)
    steamcmd = FakeSteamCmd(tmp_path / "cache")
    h.run([1, 2, 3], FakeApi({i: _item(i) for i in (1, 2, 3)}), steamcmd)
    assert [len(items) for _, items in steamcmd.calls] == [2, 1]


def test_missing_steamcmd_without_auto_install_fails(tmp_path: Path) -> None:
    h = Harness(tmp_path, auto_install_steamcmd=False)
    steamcmd = FakeSteamCmd(tmp_path / "cache")
    steamcmd.installed = False
    jobs = h.run([1], FakeApi({1: _item(1)}), steamcmd)
    assert "steamcmd was not found" in jobs[1].job.message


def test_cancel_marks_jobs_cancelled(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    cancel = threading.Event()

    def cancelling(_login: SteamLogin, _items: list[tuple[int, int]]) -> RunOutcome:
        cancel.set()
        return RunOutcome(cancelled=True)

    manager = DownloadManager(
        settings=h.settings,
        steamcmd=FakeSteamCmd(tmp_path / "cache", cancelling),
        api=FakeApi({1: _item(1)}),
        history=h.history,
        password=None,
        redactor=Redactor(),
        emit=h.events.append,
        guard_code_provider=lambda _u: None,
    )
    manager.run([1], cancel)
    assert h.finished.cancelled == 1


@pytest.mark.parametrize("mode", ["copy", "move"])
def test_existing_destination_owned_by_same_item_is_replaced(tmp_path: Path, mode: str) -> None:
    h = Harness(tmp_path, transfer_mode=mode, skip_existing=False)
    api = FakeApi({1: _item(1, "Map")})
    h.run([1], api, FakeSteamCmd(tmp_path / "cache"))
    h.run([1], api, FakeSteamCmd(tmp_path / "cache"))
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["Map"]
