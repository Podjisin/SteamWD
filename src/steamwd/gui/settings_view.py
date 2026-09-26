import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

from steamwd.config.settings import CHOICES, NAMING_PRESETS, RANGES, Settings, settings_from_dict
from steamwd.core.naming import TEMPLATE_FIELDS
from steamwd.gui.theme import Palette, style_text_widget
from steamwd.gui.widgets import ScrollableFrame

if TYPE_CHECKING:
    from steamwd.controller import Controller

__all__ = ["SettingsView"]


@dataclass(frozen=True, slots=True)
class _Field:
    name: str
    label: str
    kind: str  # "file" | "dir" | "bool" | "int" | "choice" | "text" | "template"
    help: str = ""


_CHOICE_LABELS: dict[str, dict[str, str]] = {
    "transfer_mode": {
        "copy": "Copy to output folder",
        "move": "Move to output folder",
        "leave": "Leave in steamcmd cache",
    },
    "group_by": {"none": "No grouping", "appid": "Folder per app ID", "game": "Folder per game name"},
    "login_mode": {"anonymous": "Anonymous (no account)", "account": "Steam account"},
    "theme": {"light": "Light", "dark": "Dark"},
    "log_level": {level: level.title() for level in CHOICES["log_level"]},
}

_SECTIONS: tuple[tuple[str, tuple[_Field, ...]], ...] = (
    (
        "steamcmd",
        (
            _Field("steamcmd_path", "steamcmd.exe location", "file"),
            _Field("auto_install_steamcmd", "Download steamcmd automatically if it is missing", "bool"),
            _Field("cache_dir", "Download cache folder", "dir", "steamcmd downloads here before files are placed."),
            _Field("validate_downloads", "Validate files after downloading (slower)", "bool"),
            _Field("steamcmd_timeout_minutes", "Timeout per steamcmd session (minutes)", "int"),
        ),
    ),
    (
        "Output",
        (
            _Field("output_dir", "Output folder", "dir"),
            _Field("transfer_mode", "After downloading", "choice"),
            _Field("clear_cache_after_copy", "Delete the cached copy after copying", "bool"),
            _Field("group_by", "Group items", "choice"),
            _Field(
                "naming_template",
                "Folder name",
                "template",
                "Fields: " + ", ".join(f"{{{name}}}" for name in TEMPLATE_FIELDS),
            ),
            _Field("skip_existing", "Skip items that are already downloaded and up to date", "bool"),
            _Field("expand_nested_collections", "Include collections inside collections", "bool"),
            _Field("open_output_when_done", "Open the output folder when a run finishes", "bool"),
        ),
    ),
    (
        "Steam account",
        (
            _Field("login_mode", "Login", "choice", "Some games only allow Workshop downloads for owners."),
            _Field("username", "Username", "text"),
        ),
    ),
    (
        "Queue and network",
        (
            _Field("max_retries", "Retries for failed items", "int"),
            _Field("retry_delay_seconds", "Delay between retries (seconds)", "int"),
            _Field("batch_size", "Items per steamcmd session", "int"),
            _Field("api_timeout_seconds", "Steam Web API timeout (seconds)", "int"),
        ),
    ),
    (
        "Appearance and logging",
        (
            _Field("theme", "Theme", "choice"),
            _Field("log_level", "Log level", "choice"),
            _Field("log_dir", "Log folder", "dir"),
            _Field("confirm_exit_while_running", "Ask before closing while downloads are running", "bool"),
        ),
    ),
)


class SettingsView(ttk.Frame):
    def __init__(self, master: tk.Misc, controller: "Controller") -> None:
        super().__init__(master)
        self._controller = controller
        self._vars: dict[str, tk.Variable] = {}
        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)
        body = self.scroll.body
        body.columnconfigure(0, weight=1)
        for row, (title, section_fields) in enumerate(_SECTIONS):
            frame = ttk.LabelFrame(body, text=title, padding=10)
            frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
            frame.columnconfigure(1, weight=1)
            for field_row, spec in enumerate(section_fields):
                self._build_field(frame, field_row, spec)
            if title == "Steam account":
                self._build_password(frame, len(section_fields))
        self._build_buttons()
        self.load(controller.settings)

    # ------------------------------------------------------------------ layout

    def _build_field(self, frame: ttk.LabelFrame, row: int, spec: _Field) -> None:
        if spec.kind == "bool":
            var: tk.Variable = tk.BooleanVar()
            ttk.Checkbutton(frame, text=spec.label, variable=var).grid(
                row=row, column=0, columnspan=3, sticky="w", pady=3
            )
            self._vars[spec.name] = var
            return

        ttk.Label(frame, text=spec.label).grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=3)
        cell = ttk.Frame(frame)
        cell.grid(row=row, column=1, sticky="ew", pady=3)
        cell.columnconfigure(0, weight=1)
        var = tk.StringVar()
        self._vars[spec.name] = var

        if spec.kind == "choice":
            labels = _CHOICE_LABELS[spec.name]
            ttk.Combobox(cell, textvariable=var, values=list(labels.values()), state="readonly", width=32).grid(
                row=0, column=0, sticky="w"
            )
        elif spec.kind == "int":
            low, high = RANGES[spec.name]
            ttk.Spinbox(cell, textvariable=var, from_=low, to=high, width=8).grid(row=0, column=0, sticky="w")
            ttk.Label(cell, text=f"{low}-{high}", style="Muted.TLabel").grid(row=0, column=1, sticky="w", padx=6)
        elif spec.kind == "template":
            ttk.Combobox(cell, textvariable=var, values=list(NAMING_PRESETS), width=32).grid(
                row=0, column=0, sticky="w"
            )
        else:
            ttk.Entry(cell, textvariable=var).grid(row=0, column=0, sticky="ew")
            if spec.kind in ("file", "dir"):
                ttk.Button(cell, text="Browse...", command=lambda: self._browse(spec, var)).grid(
                    row=0, column=1, padx=(6, 0)
                )
        if spec.help:
            ttk.Label(cell, text=spec.help, style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w")

    def _build_password(self, frame: ttk.LabelFrame, row: int) -> None:
        ttk.Label(frame, text="Password").grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=3)
        cell = ttk.Frame(frame)
        cell.grid(row=row, column=1, sticky="ew", pady=3)
        self.password_var = tk.StringVar()
        ttk.Entry(cell, textvariable=self.password_var, show="*", width=30).grid(row=0, column=0, sticky="w")
        ttk.Button(cell, text="Save password", command=self._save_password).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(cell, text="Remove", command=self._delete_password).grid(row=0, column=2, padx=(6, 0))
        self.password_status = ttk.Label(cell, style="Muted.TLabel")
        self.password_status.grid(row=1, column=0, columnspan=3, sticky="w")

    def _build_buttons(self) -> None:
        bar = ttk.Frame(self, padding=(12, 8))
        bar.pack(fill="x", side="bottom")
        ttk.Button(bar, text="Save", style="Accent.TButton", command=self._save).pack(side="right")
        ttk.Button(bar, text="Discard changes", command=lambda: self.load(self._controller.settings)).pack(
            side="right", padx=(0, 6)
        )
        ttk.Button(bar, text="Reset to defaults", command=self._reset).pack(side="left")
        ttk.Button(bar, text="Import...", command=self._import).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Export...", command=self._export).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Open settings folder", command=self._controller.open_settings_folder).pack(
            side="left", padx=(6, 0)
        )

    # ------------------------------------------------------------------ public

    def apply_palette(self, palette: Palette) -> None:
        style_text_widget(self.scroll.canvas, palette)

    def load(self, settings: Settings) -> None:
        """Fill the form from ``settings``."""
        for name, var in self._vars.items():
            value = getattr(settings, name)
            if name in _CHOICE_LABELS:
                var.set(_CHOICE_LABELS[name].get(value, value))
            else:
                var.set(value)
        self._refresh_password_status()

    # ---------------------------------------------------------------- handlers

    def _collect(self) -> tuple[Settings | None, list[str]]:
        data: dict[str, object] = {}
        errors: list[str] = []
        for name, var in self._vars.items():
            raw = var.get()  # type: ignore[no-untyped-call]
            if name in _CHOICE_LABELS:
                reverse = {label: key for key, label in _CHOICE_LABELS[name].items()}
                data[name] = reverse.get(str(raw), str(raw))
            elif name in RANGES:
                try:
                    data[name] = int(str(raw).strip())
                except ValueError:
                    errors.append(f"{name}: must be a whole number")
            else:
                data[name] = raw
        settings, warnings = settings_from_dict(data)
        errors += warnings
        if data.get("login_mode") == "account" and not str(data.get("username", "")).strip():
            errors.append("username: required when logging in with a Steam account")
        return (None if errors else settings), errors

    def _save(self) -> None:
        settings, errors = self._collect()
        if settings is None:
            messagebox.showerror("Invalid settings", "Please fix the following:\n\n" + "\n".join(errors))
            return
        if self._controller.save_settings(settings):
            self.load(settings)
            messagebox.showinfo("Settings", "Settings saved.")

    def _reset(self) -> None:
        if messagebox.askyesno("Reset settings", "Reset all settings to their defaults? Saved passwords are kept."):
            self.load(Settings())

    def _import(self) -> None:
        path = filedialog.askopenfilename(title="Import settings", filetypes=[("JSON", "*.json"), ("All files", "*")])
        if not path:
            return
        result = self._controller.import_settings(Path(path))
        if result is None:
            return
        settings, warnings = result
        self.load(settings)
        note = "\n\nSome values were invalid and reset:\n" + "\n".join(warnings) if warnings else ""
        messagebox.showinfo("Settings imported", f"Settings loaded into the form. Click Save to apply them.{note}")

    def _export(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export settings",
            defaultextension=".json",
            initialfile="steamwd-settings.json",
            filetypes=[("JSON", "*.json")],
        )
        if path:
            self._controller.export_settings(Path(path))

    def _browse(self, spec: _Field, var: tk.Variable) -> None:
        current = str(var.get())  # type: ignore[no-untyped-call]
        initial = str(Path(current).parent if spec.kind == "file" else current) if current else None
        if spec.kind == "file":
            chosen = filedialog.askopenfilename(
                title=spec.label, initialdir=initial, filetypes=[("steamcmd", "steamcmd.exe"), ("Programs", "*.exe")]
            )
        else:
            chosen = filedialog.askdirectory(title=spec.label, initialdir=initial, mustexist=False)
        if chosen:
            var.set(str(Path(chosen)))

    def _current_username(self) -> str:
        return str(self._vars["username"].get()).strip()  # type: ignore[no-untyped-call]

    def _save_password(self) -> None:
        username = self._current_username()
        password = self.password_var.get()
        if not username or not password:
            messagebox.showwarning("Password", "Enter a username and a password first.")
            return
        if self._controller.save_password(username, password):
            self.password_var.set("")
            self._refresh_password_status()

    def _delete_password(self) -> None:
        username = self._current_username()
        if username and self._controller.delete_password(username):
            self._refresh_password_status()

    def _refresh_password_status(self) -> None:
        username = self._current_username()
        if not username:
            text = "Enter a username to save a password."
        elif self._controller.has_password(username):
            text = f"A password for '{username}' is saved in Windows Credential Manager."
        else:
            text = "No saved password. steamcmd's cached login is used if available."
        self.password_status.configure(text=text)
