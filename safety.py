"""Windows controller ownership and an independent AUTO recovery process."""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid


def data_dir() -> Path:
    path = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "DellInspironControl"
    path.mkdir(parents=True, exist_ok=True)
    return path


def kernel():
    k = C.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateMutexW": ([C.c_void_p, W.BOOL, W.LPCWSTR], W.HANDLE),
        "ReleaseMutex": ([W.HANDLE], W.BOOL),
        "CloseHandle": ([W.HANDLE], W.BOOL),
        "CreateEventW": ([C.c_void_p, W.BOOL, W.BOOL, W.LPCWSTR], W.HANDLE),
        "OpenEventW": ([W.DWORD, W.BOOL, W.LPCWSTR], W.HANDLE),
        "SetEvent": ([W.HANDLE], W.BOOL),
        "OpenProcess": ([W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
        "WaitForSingleObject": ([W.HANDLE, W.DWORD], W.DWORD),
        "WaitForMultipleObjects": ([W.DWORD, C.POINTER(W.HANDLE), W.BOOL, W.DWORD], W.DWORD),
    }
    for name, (args, result) in signatures.items():
        fn = getattr(k, name)
        fn.argtypes, fn.restype = args, result
    return k


class HardwareLease:
    def __init__(self):
        self.k = kernel()
        C.set_last_error(0)
        self.handle = self.k.CreateMutexW(None, True, "Local\\DellFanControl006JN2")
        error = C.get_last_error()
        if not self.handle:
            raise OSError(error, "Cannot lock controller")
        if error == 183:
            self.k.CloseHandle(self.handle)
            self.handle = None
            raise RuntimeError("Another fan controller is open. Close it before using this app.")

    def close(self):
        if self.handle:
            self.k.ReleaseMutex(self.handle)
            self.k.CloseHandle(self.handle)
            self.handle = None


class RecoveryGuard:
    def __init__(self, seconds: int):
        if not isinstance(seconds, int) or not 1 <= seconds <= 3600:
            raise ValueError("Invalid recovery deadline")
        self.k = kernel()
        self.handles = []
        self.child = None
        self.log = None
        token = uuid.uuid4().hex
        try:
            for suffix in ("ready", "cancel", "heartbeat"):
                h = self.k.CreateEventW(None, suffix != "heartbeat", False,
                                        f"Local\\DellInspironControl.{token}.{suffix}")
                if not h:
                    raise OSError("Cannot create recovery event")
                self.handles.append(h)
            if getattr(sys, "frozen", False):
                command = [sys.executable]
            else:
                command = [sys.executable, str(Path(__file__).with_name("dell_control.py"))]
            self.log = (data_dir() / "recovery.log").open("a", encoding="utf-8")
            self.child = subprocess.Popen(
                [*command, "--watchdog", str(os.getpid()), str(seconds + 15), token],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=self.log,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if self.k.WaitForSingleObject(self.handles[0], 10000) != 0:
                raise RuntimeError("Recovery process did not become ready. Manual control was not entered.")
        except BaseException:
            if self.child and self.child.poll() is None:
                self.child.terminate()
                self.child.wait(timeout=5)
            self._close_handles()
            raise

    def pulse(self):
        if self.child.poll() is not None:
            raise RuntimeError("Recovery process stopped; returning AUTO")
        if not self.k.SetEvent(self.handles[2]):
            raise OSError("Cannot signal recovery process")

    def stop(self):
        # Only called after the parent has successfully restored AUTO.
        try:
            if self.child.poll() is None:
                self.k.SetEvent(self.handles[1])
                self.child.wait(timeout=5)
        finally:
            self._close_handles()

    def _close_handles(self):
        for handle in self.handles:
            self.k.CloseHandle(handle)
        self.handles.clear()
        if self.log:
            self.log.close()
            self.log = None


def watchdog(parent_pid: int, seconds: int, token: str) -> str:
    if not 1 <= parent_pid <= 0xFFFFFFFF or not 1 <= seconds <= 3615:
        raise ValueError("Invalid recovery arguments")
    if len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
        raise ValueError("Invalid recovery event token")
    from hardware import Controller

    ctrl = Controller()
    k = kernel()
    handles = []
    restore = True
    reason = "startup failure"
    try:
        parent = k.OpenProcess(0x00100000, False, parent_pid)
        if not parent:
            raise OSError("Cannot observe parent")
        handles.append(parent)
        ready = k.OpenEventW(0x0002, False, f"Local\\DellInspironControl.{token}.ready")
        cancel = k.OpenEventW(0x00100000, False, f"Local\\DellInspironControl.{token}.cancel")
        heartbeat = k.OpenEventW(0x00100000, False, f"Local\\DellInspironControl.{token}.heartbeat")
        handles.extend(h for h in (ready, cancel, heartbeat) if h)
        if not all((ready, cancel, heartbeat)) or not k.SetEvent(ready):
            raise OSError("Cannot connect recovery events")
        wait_handles = (W.HANDLE * 3)(parent, cancel, heartbeat)
        deadline = time.monotonic() + seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                reason = "absolute deadline"
                break
            status = k.WaitForMultipleObjects(3, wait_handles, False, min(5000, max(1, int(remaining * 1000))))
            if status == 0:
                reason = "parent exited"
                break
            if status == 1:
                restore = False
                return "parent restored AUTO"
            if status == 2:
                continue
            if status == 258:
                reason = "heartbeat/deadline timeout"
                break
            raise OSError(f"Recovery wait failed: {status}")
    finally:
        try:
            if restore:
                ctrl.auto()
                with (data_dir() / "recovery.log").open("a", encoding="utf-8") as log:
                    log.write(f"AUTO accepted: {reason}\n")
        finally:
            for handle in handles:
                k.CloseHandle(handle)
    return reason
