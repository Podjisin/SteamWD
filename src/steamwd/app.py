# 09/09/2026

import contextlib
import ctypes
import logging
import sys
import tkinter as tk
from tkinter import messagebox
from types import TracebackType

from steamwd import __version__

__all__ = ["main"]

logger = logging.getLogger(__name__)


def main() -> None:
    _enable_dpi_awareness()
    root = tk.Tk()
    root.title(f"SteamWD {__version__} - Steam Workshop Downloader")
    root.geometry("1100x720")
    root.minsize(820, 520)
    root.report_callback_exception = _report_error

    # Imported here so a broken import still shows a Tk error dialog above.
    from steamwd.controller import Controller

    controller = Controller(root)
    root.protocol("WM_DELETE_WINDOW", controller.on_close)
    root.mainloop()


def _enable_dpi_awareness() -> None:
    if sys.platform == "win32":
        with contextlib.suppress(AttributeError, OSError):
            ctypes.windll.shcore.SetProcessDpiAwareness(1)


def _report_error(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
    logger.error("Unhandled error in the GUI", exc_info=(exc_type, exc, tb))
    messagebox.showerror("Unexpected error", f"{exc_type.__name__}: {exc}\n\nDetails are in the log.")
