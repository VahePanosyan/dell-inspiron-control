"""One COM-owning worker thread serializes every hardware operation."""
from __future__ import annotations

import queue
import time

from PySide6.QtCore import QThread, Signal

from profiles import PROFILES
from session import ControlSession


class GpuTelemetry:
    def __init__(self):
        self.nv = self.handle = None
        try:
            import pynvml
            pynvml.nvmlInit()
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.nv = pynvml
        except Exception:
            pass

    def read(self):
        if self.nv is None:
            return {}
        try:
            n, h = self.nv, self.handle
            return {"power_w": n.nvmlDeviceGetPowerUsage(h) / 1000,
                    "limit_w": n.nvmlDeviceGetEnforcedPowerLimit(h) / 1000,
                    "temperature_c": n.nvmlDeviceGetTemperature(h, 0),
                    "utilization_pct": n.nvmlDeviceGetUtilizationRates(h).gpu}
        except Exception:
            return {}

    def close(self):
        if self.nv:
            self.nv.nvmlShutdown()


class HardwareService(QThread):
    snapshot = Signal(dict)
    event = Signal(str)
    problem = Signal(str)
    ready = Signal(bool)

    def __init__(self, demo=False):
        super().__init__()
        self.demo = demo
        self.commands = queue.Queue()

    def submit(self, name: str, seconds=300):
        if name not in (*PROFILES, "shutdown"):
            raise ValueError("Unknown command")
        if name in ("auto", "shutdown"):
            while True:
                try:
                    self.commands.get_nowait()
                except queue.Empty:
                    break
        self.commands.put((name, seconds))

    def run(self):
        if self.demo:
            self._demo()
            return
        import pythoncom
        from hardware import Controller, Thermal
        from safety import HardwareLease, RecoveryGuard

        pythoncom.CoInitialize()
        session = lease = gpu = None
        try:
            lease = HardwareLease()
            ctrl, thermal = Controller(), Thermal()
            session = ControlSession(ctrl, thermal, RecoveryGuard)
            gpu = GpuTelemetry()
            self.ready.emit(True)
            self.event.emit("Connected. No profile is applied automatically at startup.")
            next_sample = 0
            while True:
                try:
                    name, seconds = self.commands.get(timeout=.15)
                except queue.Empty:
                    name = None
                if name == "shutdown":
                    break
                if name:
                    try:
                        session.apply(name, seconds)
                        self.event.emit(f"Applied: {PROFILES[name].name}")
                        next_sample = 0
                    except Exception as exc:
                        self.problem.emit(str(exc))
                        session.auto()
                if time.monotonic() >= next_sample:
                    try:
                        status = session.tick()
                        status["gpu"] = gpu.read()
                        self.snapshot.emit(status)
                    except Exception as exc:
                        session.auto()
                        self.problem.emit(str(exc))
                    next_sample = time.monotonic() + 1
        except Exception as exc:
            self.ready.emit(False)
            self.problem.emit(str(exc))
        finally:
            try:
                if session:
                    session.auto()
                    self.event.emit("BIOS accepted AUTO on exit.")
            except Exception as exc:
                self.problem.emit(f"AUTO restore failed: {exc}. Recovery process remains active if available.")
            finally:
                if gpu:
                    gpu.close()
                if lease:
                    lease.close()
                pythoncom.CoUninitialize()

    def _demo(self):
        active, thermal, deadline = "auto", "balanced", None
        self.ready.emit(True)
        self.event.emit("DEMO — simulated telemetry; hardware is never accessed.")
        while True:
            try:
                name, seconds = self.commands.get(timeout=.4)
                if name == "shutdown":
                    return
                profile = PROFILES[name]
                active = name
                thermal = profile.thermal or thermal
                deadline = time.monotonic() + seconds if profile.level else None
                self.event.emit(f"DEMO: applied {profile.name}")
            except queue.Empty:
                pass
            if deadline and time.monotonic() >= deadline:
                active, deadline = "auto", None
                self.event.emit("DEMO: manual timer expired; AUTO restored")
            rpm = [2400, 2400] if active == "low" else [4000, 4000] if active == "high" else [5100, 4300] if active == "ultra" else [2800, 2200]
            self.snapshot.emit({"model": "Inspiron 16 Plus 7630", "board": "006JN2",
                                "fan_rpm": rpm, "temperatures_c": [68, 57], "thermal": thermal,
                                "active": active, "remaining_s": max(0, int(deadline - time.monotonic())) if deadline else None,
                                "gpu": {"power_w": 69.8 if active == "ultra" else 24.5,
                                        "limit_w": 70 if active == "ultra" else 60,
                                        "temperature_c": 62, "utilization_pct": 99 if active == "ultra" else 18}})
