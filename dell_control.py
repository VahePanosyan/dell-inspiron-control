"""Application entry point and headless recovery dispatch."""
from __future__ import annotations

import argparse
import ctypes
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Dell Inspiron Control")
    parser.add_argument("--demo", action="store_true", help="Simulated UI; never accesses hardware")
    parser.add_argument("--watchdog", nargs=3, metavar=("PID", "SECONDS", "TOKEN"), help=argparse.SUPPRESS)
    parser.add_argument("--self-test", action="store_true", help="Test GUI using simulated hardware")
    parser.add_argument("--hardware-check", action="store_true", help="Bounded live test; restores initial profile and AUTO")
    args = parser.parse_args()
    from safety import data_dir
    handler = RotatingFileHandler(data_dir() / "app.log", maxBytes=1000000, backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    if args.watchdog:
        from safety import watchdog
        watchdog(int(args.watchdog[0]), int(args.watchdog[1]), args.watchdog[2])
        return 0
    if not (args.demo or args.self_test) and not ctypes.windll.shell32.IsUserAnAdmin():
        k = ctypes.WinDLL("shell32", use_last_error=True)
        k.ShellExecuteW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                                   ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int]
        k.ShellExecuteW.restype = ctypes.c_void_p
        command = sys.argv[1:] if getattr(sys, "frozen", False) else [str(Path(__file__).resolve()), *sys.argv[1:]]
        result = k.ShellExecuteW(None, "runas", sys.executable, subprocess.list2cmdline(command), None, 1)
        return 0 if result and result > 32 else 1
    if args.hardware_check:
        from verify_app import hardware_check
        hardware_check()
        return 0
    from PySide6.QtWidgets import QApplication
    from gui import MainWindow
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Dell Inspiron Control")
    app.setStyle("Fusion")
    window = MainWindow(demo=args.demo or args.self_test)
    window.show()
    if args.self_test:
        from verify_app import gui_self_test
        gui_self_test(app, window)
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        logging.exception("Application failed")
        if not any(flag in sys.argv for flag in ("--watchdog", "--hardware-check", "--self-test")):
            ctypes.windll.user32.MessageBoxW(None, str(exc), "Dell Inspiron Control", 0x10)
        sys.exit(1)
