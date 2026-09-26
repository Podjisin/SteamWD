import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from steamwd.gui.download_view import DownloadView
from steamwd.gui.log_view import LogView
from steamwd.gui.settings_view import SettingsView
from steamwd.gui.theme import apply_theme

if TYPE_CHECKING:
    from steamwd.controller import Controller

__all__ = ["MainWindow"]


class MainWindow(ttk.Frame):
    def __init__(self, root: tk.Tk, controller: "Controller") -> None:
        super().__init__(root)
        self.root = root
        self.pack(fill="both", expand=True)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self.downloads = DownloadView(self.notebook, controller)
        self.settings = SettingsView(self.notebook, controller)
        self.log = LogView(self.notebook, controller)
        self.notebook.add(self.downloads, text="Downloads")
        self.notebook.add(self.settings, text="Settings")
        self.notebook.add(self.log, text="Log")

    def apply_theme(self, name: str) -> None:
        """Switch between light and dark themes."""
        palette = apply_theme(self.root, name)
        self.downloads.apply_palette(palette)
        self.settings.apply_palette(palette)
        self.log.apply_palette(palette)
