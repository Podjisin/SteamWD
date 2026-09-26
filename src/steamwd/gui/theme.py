"""Light and dark ttk themes."""

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

__all__ = ["PALETTES", "Palette", "apply_theme", "style_text_widget"]


@dataclass(frozen=True, slots=True)
class Palette:
    """Colors used by a theme."""

    bg: str
    fg: str
    muted: str
    field_bg: str
    field_fg: str
    button_bg: str
    button_active: str
    border: str
    accent: str
    accent_active: str
    select_bg: str
    select_fg: str
    ok: str
    error: str


PALETTES: dict[str, Palette] = {
    "light": Palette(
        bg="#f3f3f3",
        fg="#1b1b1b",
        muted="#6b6b6b",
        field_bg="#ffffff",
        field_fg="#1b1b1b",
        button_bg="#e4e4e4",
        button_active="#d6d6d6",
        border="#c8c8c8",
        accent="#1a73e8",
        accent_active="#1558b0",
        select_bg="#cce0fb",
        select_fg="#1b1b1b",
        ok="#1e7d32",
        error="#c62828",
    ),
    "dark": Palette(
        bg="#1e1f22",
        fg="#e6e6e6",
        muted="#9a9a9a",
        field_bg="#2b2d31",
        field_fg="#e6e6e6",
        button_bg="#35373c",
        button_active="#43464c",
        border="#3f4147",
        accent="#3b82f6",
        accent_active="#2563eb",
        select_bg="#2f4a73",
        select_fg="#ffffff",
        ok="#66bb6a",
        error="#ef5350",
    ),
}


def apply_theme(root: tk.Misc, name: str) -> Palette:
    """Apply a named theme to all ttk widgets and return its palette."""
    p = PALETTES.get(name, PALETTES["light"])
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(
        ".",
        background=p.bg,
        foreground=p.fg,
        fieldbackground=p.field_bg,
        bordercolor=p.border,
        darkcolor=p.bg,
        lightcolor=p.bg,
        troughcolor=p.field_bg,
        insertcolor=p.fg,
        selectbackground=p.select_bg,
        selectforeground=p.select_fg,
        focuscolor=p.accent,
    )
    style.map(".", foreground=[("disabled", p.muted)])
    style.configure("TButton", background=p.button_bg, padding=(10, 4), bordercolor=p.border)
    style.map("TButton", background=[("disabled", p.bg), ("active", p.button_active)])
    style.configure("Accent.TButton", background=p.accent, foreground="#ffffff", bordercolor=p.accent)
    style.map(
        "Accent.TButton",
        background=[("disabled", p.button_bg), ("active", p.accent_active)],
        foreground=[("disabled", p.muted)],
    )
    style.configure("TEntry", fieldbackground=p.field_bg, foreground=p.field_fg, padding=3)
    style.configure("TSpinbox", fieldbackground=p.field_bg, foreground=p.field_fg, arrowcolor=p.fg, padding=3)
    style.configure("TCombobox", fieldbackground=p.field_bg, foreground=p.field_fg, arrowcolor=p.fg, padding=3)
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", p.field_bg)],
        foreground=[("readonly", p.field_fg)],
        selectbackground=[("readonly", p.field_bg)],
        selectforeground=[("readonly", p.field_fg)],
    )
    style.configure("TCheckbutton", background=p.bg, foreground=p.fg, indicatorbackground=p.field_bg)
    style.map("TCheckbutton", background=[("active", p.bg)], indicatorbackground=[("selected", p.accent)])
    style.configure("Treeview", background=p.field_bg, fieldbackground=p.field_bg, foreground=p.field_fg, rowheight=24)
    style.map("Treeview", background=[("selected", p.select_bg)], foreground=[("selected", p.select_fg)])
    style.configure("Treeview.Heading", background=p.button_bg, foreground=p.fg, relief="flat", padding=4)
    style.map("Treeview.Heading", background=[("active", p.button_active)])
    style.configure("TNotebook", background=p.bg, borderwidth=0, tabmargins=(6, 6, 0, 0))
    style.configure("TNotebook.Tab", background=p.button_bg, foreground=p.fg, padding=(16, 6))
    style.map("TNotebook.Tab", background=[("selected", p.bg)], expand=[("selected", (1, 1, 1, 0))])
    style.configure("TLabelframe", background=p.bg, bordercolor=p.border)
    style.configure("TLabelframe.Label", background=p.bg, foreground=p.fg, font=("Segoe UI", 10, "bold"))
    style.configure("Muted.TLabel", foreground=p.muted)
    style.configure("Horizontal.TProgressbar", background=p.accent, troughcolor=p.field_bg, bordercolor=p.border)
    style.configure("TScrollbar", background=p.button_bg, troughcolor=p.bg, arrowcolor=p.fg, bordercolor=p.bg)

    root.option_add("*TCombobox*Listbox.background", p.field_bg)
    root.option_add("*TCombobox*Listbox.foreground", p.field_fg)
    root.option_add("*TCombobox*Listbox.selectBackground", p.select_bg)
    root.option_add("*TCombobox*Listbox.selectForeground", p.select_fg)
    root.option_add("*Menu.background", p.field_bg)
    root.option_add("*Menu.foreground", p.field_fg)
    if isinstance(root, tk.Tk | tk.Toplevel):
        root.configure(background=p.bg)
    return p


def style_text_widget(widget: tk.Text | tk.Canvas, p: Palette) -> None:
    """Apply palette colors to a classic Tk widget that ttk styles do not reach."""
    if isinstance(widget, tk.Canvas):
        widget.configure(background=p.bg, highlightthickness=0)
        return
    widget.configure(
        background=p.field_bg,
        foreground=p.field_fg,
        insertbackground=p.fg,
        selectbackground=p.select_bg,
        selectforeground=p.select_fg,
        relief="flat",
        highlightthickness=1,
        highlightbackground=p.border,
        highlightcolor=p.accent,
    )
