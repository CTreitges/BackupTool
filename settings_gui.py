from __future__ import annotations

import logging
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

from config import load_config, save_config, validate_config, FolderPair, Config
from ipc import read_status, restart_service, get_service_state
from datetime import datetime, timezone

_AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_AUTOSTART_NAME = "BackupTool"
_TASK_NAME = "BackupToolHeadless"


# -- Desktop autostart (Registry Run key) ------------------------------------

def _get_autostart() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOSTART_KEY, 0, winreg.KEY_READ) as k:
            winreg.QueryValueEx(k, _AUTOSTART_NAME)
            return True
    except (FileNotFoundError, OSError):
        return False


def _set_autostart(enabled: bool) -> None:
    import winreg
    if enabled:
        if getattr(sys, "frozen", False):
            value = f'"{sys.executable}"'
        else:
            tray_script = str(Path(__file__).parent / "main.py")
            value = f'"{sys.executable}" "{tray_script}" tray'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOSTART_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, _AUTOSTART_NAME, 0, winreg.REG_SZ, value)
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOSTART_KEY, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, _AUTOSTART_NAME)
        except FileNotFoundError:
            pass


# -- Server autostart (Scheduled Task, headless) -----------------------------

def _get_headless_autostart() -> bool:
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", _TASK_NAME],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def _set_headless_autostart(enabled: bool) -> None:
    if enabled:
        if getattr(sys, "frozen", False):
            exe_path = sys.executable
        else:
            exe_path = sys.executable
        if getattr(sys, "frozen", False):
            cmd = f'"{exe_path}" --headless'
        else:
            headless_script = str(Path(__file__).parent / "main.py")
            cmd = f'"{exe_path}" "{headless_script}" headless'

        # Create scheduled task that runs at system boot
        import ctypes
        ctypes.windll.shell32.ShellExecuteW(
            0, "runas", "schtasks",
            f'/Create /TN "{_TASK_NAME}" '
            f'/TR "{cmd}" '
            f'/SC ONSTART '
            f'/RU SYSTEM '
            f'/RL HIGHEST '
            f'/F',
            None, 0  # SW_HIDE
        )
    else:
        import ctypes
        ctypes.windll.shell32.ShellExecuteW(
            0, "runas", "schtasks",
            f'/Delete /TN "{_TASK_NAME}" /F',
            None, 0
        )

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
        # Use a Treeview for richer display (status per pair)
        columns = ("status", "source", "destination", "last_sync", "sync_state")
        self._pairs_tree = ttk.Treeview(parent, columns=columns, show="headings", height=8, selectmode="browse")
        self._pairs_tree.heading("status", text="")
        self._pairs_tree.heading("source", text="Source")
        self._pairs_tree.heading("destination", text="Destination")
        self._pairs_tree.heading("last_sync", text="Last Sync")
        self._pairs_tree.heading("sync_state", text="State")
        self._pairs_tree.column("status", width=30, stretch=False, anchor="center")
        self._pairs_tree.column("source", width=200, stretch=True)
        self._pairs_tree.column("destination", width=200, stretch=True)
        self._pairs_tree.column("last_sync", width=140, stretch=False, anchor="center")
        self._pairs_tree.column("sync_state", width=100, stretch=False, anchor="center")
        self._pairs_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self._refresh_pairs_list()

        btn_row = ttk.Frame(parent)
        btn_row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btn_row, text="Add...", command=self._add_pair).pack(side="left")
        ttk.Button(btn_row, text="Remove", command=self._remove_pair).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Toggle Enable/Disable", command=self._toggle_pair).pack(side="left", padx=4)

        # Auto-refresh status every 3 seconds
        self._schedule_status_refresh()

    def _schedule_status_refresh(self) -> None:
        if self._root:
            self._refresh_pairs_list()
            self._root.after(3000, self._schedule_status_refresh)

    def _format_timestamp(self, iso_str: str | None) -> str:
        if not iso_str:
            return "Never"
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.astimezone().strftime("%d.%m.%Y %H:%M")
        except Exception:
            return iso_str

    def _refresh_pairs_list(self) -> None:
        # Remember selection
        selected_id = None
        sel = self._pairs_tree.selection()
        if sel:
            selected_id = sel[0]

        self._pairs_tree.delete(*self._pairs_tree.get_children())

        status = read_status()
        pair_status = status.get("pair_status", {})

        for pair in self._config.folder_pairs:
            icon = "\u2713" if pair.enabled else "\u2717"
            ps = pair_status.get(pair.id, {})
            last_sync = self._format_timestamp(ps.get("last_sync"))
            state = ps.get("state", "unknown")

            # Show progress if scanning
            if state == "scanning":
                progress = ps.get("progress", 0)
                total = ps.get("total", 0)
                if total > 0:
                    pct = int(progress / total * 100)
                    state = f"Syncing {pct}%"
                else:
                    state = "Syncing..."
            elif state == "idle":
                state = "OK"
            elif state == "error":
                state = f"Error: {ps.get('error', '')}"

            self._pairs_tree.insert("", "end", iid=pair.id,
                                    values=(icon, pair.source, pair.destination, last_sync, state))

        # Restore selection
        if selected_id and self._pairs_tree.exists(selected_id):
            self._pairs_tree.selection_set(selected_id)

    def _add_pair(self) -> None:
        src = filedialog.askdirectory(title="Select Source Folder")
        if not src:
            return
        dst = filedialog.askdirectory(title="Select Destination Folder")
        if not dst:
            return
        self._config.folder_pairs.append(FolderPair(source=src, destination=dst))
        self._refresh_pairs_list()

        # Auto-save to trigger immediate first sync via the service's config watcher
        self._auto_save()

    def _remove_pair(self) -> None:
        sel = self._pairs_tree.selection()
        if not sel:
            return
        pair_id = sel[0]
        self._config.folder_pairs = [p for p in self._config.folder_pairs if p.id != pair_id]
        self._refresh_pairs_list()

    def _toggle_pair(self) -> None:
        sel = self._pairs_tree.selection()
        if not sel:
            return
        pair_id = sel[0]
        for pair in self._config.folder_pairs:
            if pair.id == pair_id:
                pair.enabled = not pair.enabled
                break
        self._refresh_pairs_list()

    def _auto_save(self) -> None:
        """Save config immediately so the service picks up changes and syncs."""
        errors = validate_config(self._config)
        if errors:
            return
        save_config(self._config)

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

        ttk.Separator(grid, orient="horizontal").grid(row=3, column=0, columnspan=2, sticky="ew", pady=12)

        self._autostart_var = tk.BooleanVar(value=_get_autostart())
        ttk.Checkbutton(grid, text="Autostart mit Tray-Icon (Desktop)",
                        variable=self._autostart_var).grid(row=4, column=0, columnspan=2, sticky="w", pady=4)

        self._headless_var = tk.BooleanVar(value=_get_headless_autostart())
        ttk.Checkbutton(grid, text="Autostart Headless Mode (Server, kein GUI, startet bei Systemboot)",
                        variable=self._headless_var).grid(row=5, column=0, columnspan=2, sticky="w", pady=4)

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
            _set_autostart(self._autostart_var.get())
        except Exception as e:
            messagebox.showwarning("Autostart", f"Could not update autostart setting:\n{e}")

        try:
            _set_headless_autostart(self._headless_var.get())
        except Exception as e:
            messagebox.showwarning("Headless Autostart", f"Could not update headless autostart:\n{e}")

        messagebox.showinfo("Saved", "Configuration saved. Changes will be applied automatically.")

        if self._root:
            self._root.destroy()
