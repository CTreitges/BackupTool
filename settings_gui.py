from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from config import load_config, save_config, validate_config, FolderPair, Config
from ipc import read_status, restart_service, get_service_state

log = logging.getLogger(__name__)


class SettingsWindow:
    def __init__(self) -> None:
        self._config: Config = load_config()
        self._root: tk.Tk | None = None

    def run(self) -> None:
        self._root = tk.Tk()
        self._root.title("BackupTool Settings")
        self._root.resizable(True, True)
        self._build_ui()
        self._root.mainloop()

    def _build_ui(self) -> None:
        root = self._root
        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # Tab 1 – Folder Pairs
        pairs_frame = ttk.Frame(nb)
        nb.add(pairs_frame, text="Folder Pairs")
        self._build_pairs_tab(pairs_frame)

        # Tab 2 – Settings
        settings_frame = ttk.Frame(nb)
        nb.add(settings_frame, text="Settings")
        self._build_settings_tab(settings_frame)

        # Tab 3 – Status
        status_frame = ttk.Frame(nb)
        nb.add(status_frame, text="Status")
        self._build_status_tab(status_frame)

        # Bottom bar
        bar = ttk.Frame(root)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(bar, text="Save & Restart Service", command=self._save_and_restart).pack(side="right")
        ttk.Button(bar, text="Cancel", command=root.destroy).pack(side="right", padx=4)

    # ------------------------------------------------------------------
    # Tab: Folder Pairs
    # ------------------------------------------------------------------

    def _build_pairs_tab(self, parent: ttk.Frame) -> None:
        self._pairs_list = tk.Listbox(parent, selectmode=tk.SINGLE, height=8)
        self._pairs_list.pack(fill="both", expand=True, padx=8, pady=8)
        self._refresh_pairs_list()

        btn_row = ttk.Frame(parent)
        btn_row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btn_row, text="Add…", command=self._add_pair).pack(side="left")
        ttk.Button(btn_row, text="Remove", command=self._remove_pair).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Toggle Enable/Disable", command=self._toggle_pair).pack(side="left", padx=4)

    def _refresh_pairs_list(self) -> None:
        self._pairs_list.delete(0, tk.END)
        for pair in self._config.folder_pairs:
            state = "✓" if pair.enabled else "✗"
            self._pairs_list.insert(tk.END, f"[{state}] {pair.source}  →  {pair.destination}")

    def _add_pair(self) -> None:
        src = filedialog.askdirectory(title="Select Source Folder")
        if not src:
            return
        dst = filedialog.askdirectory(title="Select Destination Folder")
        if not dst:
            return
        self._config.folder_pairs.append(FolderPair(source=src, destination=dst))
        self._refresh_pairs_list()

    def _remove_pair(self) -> None:
        sel = self._pairs_list.curselection()
        if not sel:
            return
        idx = sel[0]
        del self._config.folder_pairs[idx]
        self._refresh_pairs_list()

    def _toggle_pair(self) -> None:
        sel = self._pairs_list.curselection()
        if not sel:
            return
        idx = sel[0]
        pair = self._config.folder_pairs[idx]
        pair.enabled = not pair.enabled
        self._refresh_pairs_list()

    # ------------------------------------------------------------------
    # Tab: Settings
    # ------------------------------------------------------------------

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        grid = ttk.Frame(parent)
        grid.pack(padx=16, pady=16, anchor="nw")

        ttk.Label(grid, text="Retention (days):").grid(row=0, column=0, sticky="w", pady=4)
        self._retention_var = tk.IntVar(value=self._config.retention_days)
        ttk.Spinbox(grid, from_=1, to=3650, textvariable=self._retention_var, width=8).grid(
            row=0, column=1, sticky="w", padx=8
        )

        ttk.Label(grid, text="Scan Interval (min):").grid(row=1, column=0, sticky="w", pady=4)
        self._scan_var = tk.IntVar(value=self._config.scan_interval_minutes)
        ttk.Spinbox(grid, from_=1, to=1440, textvariable=self._scan_var, width=8).grid(
            row=1, column=1, sticky="w", padx=8
        )

        ttk.Label(grid, text="Log Level:").grid(row=2, column=0, sticky="w", pady=4)
        self._log_level_var = tk.StringVar(value=self._config.log_level)
        ttk.Combobox(
            grid,
            textvariable=self._log_level_var,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            state="readonly",
            width=10,
        ).grid(row=2, column=1, sticky="w", padx=8)

    # ------------------------------------------------------------------
    # Tab: Status
    # ------------------------------------------------------------------

    def _build_status_tab(self, parent: ttk.Frame) -> None:
        status = read_status()
        svc_state = get_service_state()

        text = tk.Text(parent, wrap="word", state="disabled", height=15)
        text.pack(fill="both", expand=True, padx=8, pady=8)

        lines = [f"Service state: {svc_state}"]
        for k, v in status.items():
            lines.append(f"{k}: {v}")

        text.config(state="normal")
        text.insert("end", "\n".join(lines))
        text.config(state="disabled")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save_and_restart(self) -> None:
        # Apply settings tab values back to config
        try:
            self._config.retention_days = int(self._retention_var.get())
            self._config.scan_interval_minutes = int(self._scan_var.get())
            self._config.log_level = self._log_level_var.get()
        except Exception as e:
            messagebox.showerror("Validation Error", str(e))
            return

        errors = validate_config(self._config)
        if errors:
            messagebox.showerror("Validation Errors", "\n".join(errors))
            return

        save_config(self._config)

        try:
            restart_service()
            messagebox.showinfo("Saved", "Configuration saved and service restarted.")
        except Exception as e:
            messagebox.showwarning("Saved", f"Configuration saved but could not restart service:\n{e}")

        if self._root:
            self._root.destroy()
