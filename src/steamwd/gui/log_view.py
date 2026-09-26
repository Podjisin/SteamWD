import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from typing import TYPE_CHECKING

from steamwd.gui.theme import Palette, style_text_widget

if TYPE_CHECKING:
    from steamwd.controller import Controller

__all__ = ["LogView"]

_MAX_LINES = 5000


class LogView(ttk.Frame):
    def __init__(self, master: tk.Misc, controller: "Controller") -> None:
        super().__init__(master, padding=10)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 6))
        self.autoscroll = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Auto-scroll", variable=self.autoscroll).pack(side="left")
        ttk.Button(bar, text="Open log folder", command=controller.open_log_folder).pack(side="right")
        ttk.Button(bar, text="Copy all", command=self._copy_all).pack(side="right", padx=(0, 6))
        ttk.Button(bar, text="Clear", command=self.clear).pack(side="right", padx=(0, 6))
        self.text = ScrolledText(self, wrap="none", font=("Consolas", 9), state="disabled")
        self.text.pack(fill="both", expand=True)

    def apply_palette(self, palette: Palette) -> None:
        style_text_widget(self.text, palette)
        self.text.tag_configure("error", foreground=palette.error)
        self.text.tag_configure("warning", foreground="#e0a100")

    def append(self, line: str) -> None:
        """Append a log line, trimming old lines."""
        tag = "error" if " ERROR " in line else "warning" if " WARNING " in line else ""
        self.text.configure(state="normal")
        self.text.insert("end", line + "\n", tag)
        excess = int(self.text.index("end-1c").split(".")[0]) - _MAX_LINES
        if excess > 0:
            self.text.delete("1.0", f"{excess + 1}.0")
        self.text.configure(state="disabled")
        if self.autoscroll.get():
            self.text.see("end")

    def clear(self) -> None:
        """Remove all lines from the view (log files are kept)."""
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def _copy_all(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.text.get("1.0", "end-1c"))
