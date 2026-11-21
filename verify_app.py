"""Explicit opt-in checks for the built application."""
import json
import time

from safety import data_dir


def gui_self_test(app, window):
    from PySide6.QtCore import Qt, QTimer, QPoint
    from PySide6.QtTest import QTest
    app.setQuitOnLastWindowClosed(False)

    def wait(predicate, timeout=5):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if predicate():
                return
            QTest.qWait(40)
        raise AssertionError("GUI condition timed out")

    def run():
        result = {"demo": True, "passed": False}
        try:
            wait(lambda: window.connected and bool(window.latest))
            for profile in ("low", "high", "ultra", "balanced"):
                QTest.mouseClick(window.presets[profile], Qt.MouseButton.LeftButton)
                QTest.mouseClick(window.apply_button, Qt.MouseButton.LeftButton)
                wait(lambda: window.latest.get("active") == profile)
            window.presets["ultra"].click()
            window.apply_selected()
            wait(lambda: window.latest.get("active") == "ultra")
            window.language.setCurrentIndex(1)
            QTest.qWait(150)
            assert window.latest["gpu"]["limit_w"] == 70
            assert window.grab().save(str(data_dir() / "gui-preview.png"))
            window.resize(980, 770)
            QTest.qWait(150)
            for control in [*window.presets.values(), window.auto_button, window.apply_button,
                            window.duration, window.log, window.language]:
                position = control.mapTo(window, QPoint(0, 0))
                assert control.isVisible() and position.y() + control.height() <= window.height(), control.objectName()
                assert position.x() + control.width() <= window.width()
            QTest.mouseClick(window.auto_button, Qt.MouseButton.LeftButton)
            wait(lambda: window.latest.get("active") == "auto")
            result.update(passed=True, profiles_tested=["low", "high", "ultra", "balanced", "auto"],
                          compact_size=[window.width(), window.height()])
        except Exception as exc:
            result["error"] = repr(exc)
            window.grab().save(str(data_dir() / "gui-failure.png"))
        finally:
            (data_dir() / "gui-check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            window.worker.finished.connect(lambda: app.exit(0 if result["passed"] else 1))
            window.close()

    QTimer.singleShot(100, run)


def hardware_check():
    from hardware import Controller, Thermal
    from safety import RecoveryGuard
    from service import GpuTelemetry
    from session import ControlSession

    ctrl, thermal = Controller(), Thermal()
    original = thermal.status()["current"]
    report = {"passed": False, "initial_profile": original, "samples": []}
    session = ControlSession(ctrl, thermal, RecoveryGuard)
    try:
        session.apply("ultra", 3)
        assert thermal.status()["current"] == "performance"
        report["ultra"] = session.tick()
        session.apply("high", 3)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            report["samples"].append(session.tick())
            time.sleep(.4)
        assert session.level is None
        report["timer_auto"] = True
        recovery_log = data_dir() / "recovery.log"
        start_size = recovery_log.stat().st_size if recovery_log.exists() else 0
        session.apply("high", 20)
        # Deliberately stop heartbeats while the parent is alive.
        deadline = time.monotonic() + 9
        while session.guard.child.poll() is None and time.monotonic() < deadline:
            time.sleep(.2)
        assert session.guard.child.poll() == 0
        new_log = recovery_log.read_bytes()[start_size:].decode("utf-8")
        assert "AUTO accepted: heartbeat/deadline timeout" in new_log
        report["heartbeat_recovery"] = True
        session.auto()
        report["passed"] = True
    except Exception as exc:
        report["error"] = repr(exc)
        raise
    finally:
        try:
            session.auto()
            thermal.set_mode(original)
            report["final_profile"] = thermal.status()["current"]
            report["final_status"] = ctrl.status()
            report["auto_accepted"] = True
        finally:
            (data_dir() / "hardware-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
