"""Filesystem operations for downloaded content."""

import os
import shutil
from pathlib import Path

__all__ = ["open_in_explorer", "remove_tree", "transfer"]


def transfer(source: Path, destination: Path, mode: str) -> Path:
    """Copy or move a downloaded item folder, replacing any existing destination.

    Args:
        source: The folder steamcmd downloaded into.
        destination: Target folder.
        mode: ``"copy"`` or ``"move"``.

    Returns:
        The destination path.
    """
    if source.resolve() == destination.resolve():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        remove_tree(destination)
    if mode == "move":
        shutil.move(str(source), str(destination))
    else:
        shutil.copytree(source, destination)
    return destination


def remove_tree(path: Path) -> None:
    """Delete a folder (or file) if it exists."""
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def open_in_explorer(path: Path) -> None:
    """Open a folder in Windows Explorer, creating it first if needed."""
    path.mkdir(parents=True, exist_ok=True)
    os.startfile(path)  # noqa: S606 - Windows-only app
