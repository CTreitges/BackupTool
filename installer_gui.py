"""
BackupTool GUI-Installer
========================
Run with:  python installer_gui.py
Or:        double-click via a .bat launcher

Requires no admin until the actual install step (self-elevates via UAC).
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

SCRIPT_DIR = Path(__file__).parent
PYTHON_EXE = SCRIPT_DIR / ".venv" / "Scripts" / "python.exe"
INSTALL_PS1 = SCRIPT_DIR / "install.ps1"
UNINSTALL_PS1 = SCRIPT_DIR / "uninstall.ps1"


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def self_elevate() -> None:
    """Re-launch this script with UAC elevation."""
    script = str(Path(__file__).resolve())
    params = f'"{sys.executable}" "{script}"'
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, script, None, 1)
    sys.exit(0)


class InstallerApp:
    def __init__(self) -> None:
        self._root = tk.Tk()
        self._root.title("BackupTool Setup")
        self._root.resizable(False, False)
        self._log_lines: list[str] = []
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = self._root

        # Header
        hdr = tk.Frame(root, bg="#1e3a5f", pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text="BackupTool", font=("Segoe UI", 18, "bold"),
                 bg="#1e3a5f", fg="white").pack()
        tk.Label(hdr, text="Folder sync with recycle bin  ·  Windows Service + Tray",
                 font=("Segoe UI", 9), bg="#1e3a5f", fg="#a0c4e8").pack()

        # Info grid
        info = ttk.LabelFrame(root, text="Installation details", padding=10)
        info.pack(fill="x", padx=16, pady=(12, 4))

        rows = [
            ("Install directory", str(SCRIPT_DIR)),
            ("Python", str(PYTHON_EXE)),
            ("Config", r"C:\ProgramData\BackupTool\config.json"),
            ("Service", "BackupToolSvc  (auto-start)"),
            ("Tray autostart", "HKCU Run  →  tray icon on login"),
        ]
        for i, (label, value) in enumerate(rows):
            ttk.Label(info, text=label + ":", font=("Segoe UI", 9, "bold")).grid(
                row=i, column=0, sticky="w", pady=2, padx=(0, 8))
            ttk.Label(info, text=value, font=("Segoe UI", 9),
                      foreground="#444").grid(row=i, column=1, sticky="w")

        # Pre-flight checks
        self._checks_frame = ttk.LabelFrame(root, text="Pre-flight checks", padding=10)
        self._checks_frame.pack(fill="x", padx=16, pady=4)
        self._check_labels: dict[str, tk.Label] = {}
        checks = [
            ("venv", ".venv exists"),
            ("python", "Python 3.10+"),
            ("ps1", "install.ps1 present"),
            ("admin", "Administrator rights"),
        ]
        for col, (key, text) in enumerate(checks):
            lbl = tk.Label(self._checks_frame, text=f"⏳ {text}",
                           font=("Segoe UI", 9), anchor="w")
            lbl.grid(row=0, column=col, sticky="w", padx=8)
            self._check_labels[key] = lbl

        # Log output
        log_frame = ttk.LabelFrame(root, text="Log", padding=6)
        log_frame.pack(fill="both", expand=True, padx=16, pady=4)
        self._log = tk.Text(log_frame, height=10, state="disabled",
                            font=("Consolas", 9), bg="#0d1117", fg="#c9d1d9",
                            relief="flat", wrap="word")
        sb = ttk.Scrollbar(log_frame, command=self._log.yview)
        self._log.configure(yscrollcommand=sb.set)
        self._log.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Buttons
        btn_row = tk.Frame(root, pady=10)
        btn_row.pack()
        self._install_btn = ttk.Button(btn_row, text="Install", width=16,
                                       command=self._on_install)
        self._install_btn.pack(side="left", padx=6)
        self._uninstall_btn = ttk.Button(btn_row, text="Uninstall", width=16,
                                         command=self._on_uninstall)
        self._uninstall_btn.pack(side="left", padx=6)
        ttk.Button(btn_row, text="Close", width=10,
                   command=self._root.destroy).pack(side="left", padx=6)

        self._status_var = tk.StringVar(value="Ready.")
        ttk.Label(root, textvariable=self._status_var,
                  font=("Segoe UI", 9), foreground="#555").pack(pady=(0, 8))

        # Run checks
        self._root.after(200, self._run_checks)

    # ── Pre-flight checks ────────────────────────────────────────────────────

    def _run_checks(self) -> None:
        all_ok = True

        def check(key: str, ok: bool, ok_text: str, fail_text: str) -> None:
            nonlocal all_ok
            lbl = self._check_labels[key]
            if ok:
                lbl.config(text=f"✓ {ok_text}", fg="#2ea043")
            else:
                lbl.config(text=f"✗ {fail_text}", fg="#f85149")
                all_ok = False

        check("venv", PYTHON_EXE.exists(), ".venv OK", ".venv missing")

        py_ok = False
        if PYTHON_EXE.exists():
            try:
                r = subprocess.run([str(PYTHON_EXE), "--version"],
                                   capture_output=True, text=True, timeout=5)
                ver = r.stdout.strip() or r.stderr.strip()
                py_ok = True
                self._check_labels["python"].config(
                    text=f"✓ {ver}", fg="#2ea043")
            except Exception:
                pass
        if not py_ok:
            self._check_labels["python"].config(text="✗ Python error", fg="#f85149")
            all_ok = False

        check("ps1", INSTALL_PS1.exists(), "install.ps1 OK", "install.ps1 missing")
        check("admin", is_admin(), "Admin ✓", "No admin (will ask)")

        if not all_ok:
            self._status_var.set("Some checks failed – see above.")

    # ── Logging ──────────────────────────────────────────────────────────────

    def _append_log(self, text: str, color: str = "#c9d1d9") -> None:
        def _do():
            self._log.config(state="normal")
            self._log.insert("end", text + "\n", ("col",))
            self._log.tag_config("col", foreground=color)
            # Re-apply color only to newly inserted text via a tag per line
            idx = self._log.index("end-2l")
            tag = f"t{len(self._log_lines)}"
            self._log.tag_add(tag, idx, "end-1c")
            self._log.tag_config(tag, foreground=color)
            self._log.config(state="disabled")
            self._log.see("end")
        self._root.after(0, _do)
        self._log_lines.append(text)

    # ── Actions ──────────────────────────────────────────────────────────────

    def _on_install(self) -> None:
        if not is_admin():
            if messagebox.askyesno(
                "Admin required",
                "Installation requires administrator privileges.\n\n"
                "Click Yes to restart as admin (UAC prompt will appear)."
            ):
                self_elevate()
            return
        self._run_ps_script(INSTALL_PS1, "install")

    def _on_uninstall(self) -> None:
        if not messagebox.askyesno("Confirm", "Uninstall BackupTool service and autostart?"):
            return
        if not is_admin():
            if messagebox.askyesno(
                "Admin required",
                "Uninstallation requires administrator privileges.\n\n"
                "Click Yes to restart as admin (UAC prompt will appear)."
            ):
                self_elevate()
            return
        self._run_ps_script(UNINSTALL_PS1, "uninstall")

    def _run_ps_script(self, script: Path, action: str) -> None:
        self._install_btn.config(state="disabled")
        self._uninstall_btn.config(state="disabled")
        self._status_var.set(f"Running {action}…")
        self._append_log(f"=== Starting {action} ===", "#58a6ff")

        def worker():
            try:
                proc = subprocess.Popen(
                    ["powershell.exe", "-ExecutionPolicy", "Bypass",
                     "-File", str(script)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                for line in proc.stdout:
                    line = line.rstrip()
                    if not line:
                        continue
                    color = "#2ea043" if "OK" in line else \
                            "#f85149" if "FAIL" in line or "error" in line.lower() else \
                            "#e3b341" if "WARN" in line or "warn" in line.lower() else \
                            "#c9d1d9"
                    self._append_log(line, color)
                proc.wait()
                success = proc.returncode == 0
                self._root.after(0, lambda: self._on_done(success, action))
            except Exception as exc:
                self._append_log(f"ERROR: {exc}", "#f85149")
                self._root.after(0, lambda: self._on_done(False, action))

        threading.Thread(target=worker, daemon=True).start()

    def _on_done(self, success: bool, action: str) -> None:
        self._install_btn.config(state="normal")
        self._uninstall_btn.config(state="normal")
        if success:
            self._status_var.set(f"{action.capitalize()} completed successfully.")
            self._append_log(f"=== {action.capitalize()} complete ===", "#2ea043")
        else:
            self._status_var.set(f"{action.capitalize()} finished with errors.")
            self._append_log(f"=== {action.capitalize()} finished with errors ===", "#f85149")

    # ── Run ──────────────────────────────────────────────────────────────────

    def run(self) -> None:
        # Centre on screen
        self._root.update_idletasks()
        w, h = 700, 560
        x = (self._root.winfo_screenwidth() - w) // 2
        y = (self._root.winfo_screenheight() - h) // 2
        self._root.geometry(f"{w}x{h}+{x}+{y}")
        self._root.mainloop()


if __name__ == "__main__":
    InstallerApp().run()
