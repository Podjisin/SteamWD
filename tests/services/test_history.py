from pathlib import Path

from steamwd.services.history import DownloadHistory


def test_record_persist_and_owner(tmp_path: Path) -> None:
    history = DownloadHistory(tmp_path / "h.json")
    history.record(item_id=1, title="A", app_id=4000, time_updated=5, path=tmp_path / "out" / "A")
    reloaded = DownloadHistory(tmp_path / "h.json")
    reloaded.load()
    entry = reloaded.get(1)
    assert entry is not None
    assert entry.time_updated == 5
    assert reloaded.owner_of(tmp_path / "out" / "A") == 1
    assert reloaded.owner_of(tmp_path / "out" / "B") is None


def test_corrupt_history_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "h.json"
    path.write_text("garbage", encoding="utf-8")
    history = DownloadHistory(path)
    history.load()
    assert history.get(1) is None
