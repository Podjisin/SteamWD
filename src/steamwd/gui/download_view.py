import tkinter as tk
import webbrowser
from collections.abc import Iterable
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from steamwd.core.models import DownloadJob, JobStatus, workshop_url
from steamwd.gui.theme import Palette, style_text_widget
from steamwd.gui.widgets import format_size

if TYPE_CHECKING:
    from steamwd.controller import Controller

__all__ = ["DownloadView"]

_COLUMNS = (
    ("item_id", "ID", 110, False),
    ("app_id", "App", 70, False),
    ("size", "Size", 80, False),
    ("status", "Status", 100, False),
    ("progress", "Progress", 85, False),
    ("message", "Details", 360, True),
)


class DownloadView(ttk.Frame):
    """The main download queue screen."""

    def __init__(self, master: tk.Misc, controller: "Controller") -> None:
        super().__init__(master, padding=10)
        self._controller = controller
        self._build_input()
        self._build_toolbar()
        self._build_table()
        self._build_status_bar()
        self.set_running(False)

    # ------------------------------------------------------------------ layout

    def _build_input(self) -> None:
        frame = ttk.LabelFrame(self, text="Add Workshop items or collections", padding=8)
        frame.pack(fill="x")
        ttk.Label(
            frame,
            text="Paste links or IDs (one per line, or separated by spaces or commas).",
            style="Muted.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        self.input_text = tk.Text(frame, height=4, wrap="none", undo=True, font=("Consolas", 10))
        self.input_text.grid(row=1, column=0, sticky="nsew")
        self.input_text.bind("<Control-Return>", self._on_ctrl_enter)
        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=1, sticky="ns", padx=(8, 0))
        ttk.Button(buttons, text="Add to queue", command=self._on_add).pack(fill="x")
        ttk.Button(buttons, text="Add and start", style="Accent.TButton", command=lambda: self._on_add(True)).pack(
            fill="x", pady=(6, 0)
        )
        ttk.Button(buttons, text="Paste", command=self._paste).pack(fill="x", pady=(6, 0))
        frame.columnconfigure(0, weight=1)

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(10, 6))
        self.start_button = ttk.Button(bar, text="Start", style="Accent.TButton", command=self._controller.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(bar, text="Stop", command=self._controller.stop)
        self.stop_button.pack(side="left", padx=(6, 0))
        self.retry_button = ttk.Button(bar, text="Retry failed", command=self._controller.retry_failed)
        self.retry_button.pack(side="left", padx=(6, 0))
        self.remove_button = ttk.Button(bar, text="Remove selected", command=self._remove_selected)
        self.remove_button.pack(side="left", padx=(6, 0))
        self.clear_button = ttk.Button(bar, text="Clear finished", command=self._controller.clear_finished)
        self.clear_button.pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Open output folder", command=self._controller.open_output_folder).pack(side="right")

    def _build_table(self) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=[c[0] for c in _COLUMNS], selectmode="extended")
        self.tree.heading("#0", text="Title")
        self.tree.column("#0", width=320, minwidth=160, stretch=True)
        for key, label, width, stretch in _COLUMNS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=50, stretch=stretch)
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<Delete>", lambda _e: self._remove_selected())

        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label="Open folder", command=self._open_selected_folder)
        self.menu.add_command(label="Open Workshop page", command=self._open_selected_page)
        self.menu.add_command(label="Copy ID", command=self._copy_selected_ids)
        self.menu.add_separator()
        self.menu.add_command(label="Remove", command=self._remove_selected)

    def _build_status_bar(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(8, 0))
        self.progress = ttk.Progressbar(bar, mode="determinate", length=240)
        self.progress.pack(side="left")
        self.status_label = ttk.Label(bar, text="Queue is empty")
        self.status_label.pack(side="left", padx=(10, 0))

    # ------------------------------------------------------------------ public

    def apply_palette(self, palette: Palette) -> None:
        style_text_widget(self.input_text, palette)
        self.tree.tag_configure("failed", foreground=palette.error)
        self.tree.tag_configure("done", foreground=palette.ok)
        self.tree.tag_configure("muted", foreground=palette.muted)
        self.tree.tag_configure("normal", foreground=palette.field_fg)

    def upsert_job(self, job: DownloadJob) -> None:
        iid = str(job.item_id)
        title = job.title or ("(collection)" if job.is_collection else "")
        if job.is_collection:
            title = f"[Collection] {title}".strip()
        values = (
            job.item_id,
            job.app_id or "",
            format_size(job.file_size),
            job.status.value,
            f"{job.progress}%" if job.progress is not None else "--",
            job.message,
        )
        tag = _tag_for(job.status)
        if self.tree.exists(iid):
            self.tree.item(iid, text=title, values=values, tags=(tag,))
            return
        parent = str(job.source_collection) if job.source_collection else ""
        if parent and not self.tree.exists(parent):
            parent = ""
        self.tree.insert(parent, "end", iid=iid, text=title, values=values, tags=(tag,), open=True)

    def remove_rows(self, item_ids: Iterable[int]) -> None:
        """Remove rows (children of removed rows are removed too)."""
        for item_id in item_ids:
            iid = str(item_id)
            if self.tree.exists(iid):
                self.tree.delete(iid)

    def set_running(self, running: bool) -> None:
        """Enable or disable controls according to whether a run is active."""
        self.start_button.state(["disabled"] if running else ["!disabled"])
        self.stop_button.state(["!disabled"] if running else ["disabled"])
        self.retry_button.state(["disabled"] if running else ["!disabled"])
        self.clear_button.state(["disabled"] if running else ["!disabled"])

    def set_summary(self, total: int, finished: int, text: str) -> None:
        self.progress.configure(maximum=max(total, 1), value=finished)
        self.status_label.configure(text=text)

    # ---------------------------------------------------------------- handlers

    def _on_add(self, start: bool = False) -> None:
        text = self.input_text.get("1.0", "end")
        added, invalid = self._controller.add_inputs(text)
        if invalid:
            preview = "\n".join(invalid[:10]) + ("\n..." if len(invalid) > 10 else "")
            messagebox.showwarning(
                "Some input was not recognised", f"These were not Workshop links or IDs:\n\n{preview}"
            )
        if added or not invalid:
            self.input_text.delete("1.0", "end")
        if start:
            self._controller.start()

    def _on_ctrl_enter(self, _event: "tk.Event[tk.Text]") -> str:
        self._on_add(start=True)
        return "break"

    def _paste(self) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return
        self.input_text.insert("end", text.strip() + "\n")

    def _selected_ids(self) -> list[int]:
        return [int(iid) for iid in self.tree.selection()]

    def _remove_selected(self) -> None:
        self._controller.remove_jobs(self._selected_ids())

    def _on_double_click(self, event: "tk.Event[ttk.Treeview]") -> None:
        iid = self.tree.identify_row(event.y)
        if iid:
            self._controller.open_job(int(iid))

    def _on_right_click(self, event: "tk.Event[ttk.Treeview]") -> None:
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        if iid not in self.tree.selection():
            self.tree.selection_set(iid)
        self.menu.tk_popup(event.x_root, event.y_root)

    def _open_selected_folder(self) -> None:
        for item_id in self._selected_ids()[:5]:
            self._controller.open_job(item_id)

    def _open_selected_page(self) -> None:
        for item_id in self._selected_ids()[:5]:
            webbrowser.open(workshop_url(item_id))

    def _copy_selected_ids(self) -> None:
        self.clipboard_clear()
        self.clipboard_append("\n".join(str(i) for i in self._selected_ids()))


def _tag_for(status: JobStatus) -> str:
    if status is JobStatus.FAILED:
        return "failed"
    if status is JobStatus.DONE:
        return "done"
    if status in (JobStatus.SKIPPED, JobStatus.CANCELLED):
        return "muted"
    return "normal"
