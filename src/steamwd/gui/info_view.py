"""Project information and community links."""

import tkinter as tk
import webbrowser
from tkinter import ttk

from steamwd import __version__
from steamwd.gui.theme import Palette, style_text_widget

__all__ = ["InfoView"]

_REPOSITORY = "https://github.com/Podjisin/SteamWD"
_LICENSE_TEXT = """DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
Version 2, December 2004

Copyright (C) 2026 Podjisin

Everyone is permitted to copy and distribute verbatim or modified
copies of this license document, and changing it is allowed as long
as the name is changed.

DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION

0. You just DO WHAT THE FUCK YOU WANT TO.
"""


class InfoView(ttk.Frame):
    """Show project details and links for help and contributions."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=24)
        self._link_labels: list[ttk.Label] = []
        self._license_text: tk.Text
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text="SteamWD", font=("Segoe UI", 22, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(self, text=f"Version {__version__}", style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 18)
        )
        ttk.Label(
            self,
            text="This is just another steam workshop downloader.",
            wraplength=620,
            justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(0, 18))

        links = ttk.LabelFrame(self, text="Project", padding=12)
        links.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        links.columnconfigure(1, weight=1)
        self._add_link(links, 0, "GitHub repository", "Browse the source code and releases.", _REPOSITORY)
        self._add_link(links, 1, "Report an issue", "Report bugs or request improvements.", f"{_REPOSITORY}/issues/new")
        self._add_link(
            links,
            2,
            "Contribute",
            "Read the contribution guide and add game processors.",
            f"{_REPOSITORY}/blob/main/CONTRIBUTING.md",
        )
        self._add_link(links, 3, "License", "View the project license.", f"{_REPOSITORY}/blob/main/LICENSE")

        license_frame = ttk.LabelFrame(self, text="License", padding=12)
        license_frame.grid(row=4, column=0, sticky="nsew", pady=(0, 12))
        license_frame.columnconfigure(0, weight=1)
        license_frame.rowconfigure(0, weight=1)
        self._license_text = tk.Text(license_frame, height=9, width=80, wrap="word", font=("Consolas", 9))
        self._license_text.insert("1.0", _LICENSE_TEXT)
        self._license_text.configure(state="disabled")
        self._license_text.grid(row=0, column=0, sticky="nsew")
        license_scroll = ttk.Scrollbar(license_frame, orient="vertical", command=self._license_text.yview)
        license_scroll.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        self._license_text.configure(yscrollcommand=license_scroll.set)
        ttk.Label(
            license_frame,
            text="Licensed under the WTFPL v2. Read the full license above or view the canonical file on GitHub.",
            style="Muted.TLabel",
            wraplength=620,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        processing = ttk.LabelFrame(self, text="Supported game processing", padding=12)
        processing.grid(row=5, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(
            processing,
            text=(
                "SteamWD routes Workshop items automatically by game. Stellaris and RimWorld have "
                "dedicated processors; unsupported games use the generic output flow. "
                "Community processors are welcome."
            ),
            wraplength=620,
            justify="left",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(0, 12))

        ttk.Label(
            self,
            text="SteamWD is open source software. Check the repository for documentation, releases, and development updates.",
            style="Muted.TLabel",
            wraplength=620,
            justify="left",
        ).grid(row=6, column=0, sticky="w", pady=(4, 0))

    def _add_link(self, parent: ttk.LabelFrame, row: int, title: str, description: str, url: str) -> None:
        ttk.Label(parent, text=title).grid(row=row, column=0, sticky="w", padx=(0, 16), pady=4)
        link = ttk.Label(parent, text=description, style="Link.TLabel", cursor="hand2")
        link.grid(row=row, column=1, sticky="w", pady=4)
        link.bind("<Button-1>", lambda _event: webbrowser.open(url))
        self._link_labels.append(link)

    def apply_palette(self, palette: Palette) -> None:
        """Apply palette colors to the clickable links."""
        for label in self._link_labels:
            label.configure(foreground=palette.accent)
        style_text_widget(self._license_text, palette)
        self._license_text.configure(state="disabled")
