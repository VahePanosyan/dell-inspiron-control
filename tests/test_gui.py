import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from gui import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def wait_for(predicate, seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        QTest.qWait(30)
    raise AssertionError("UI condition not reached")


@pytest.fixture
def window(app):
    window = MainWindow(demo=True)
    window.show()
    wait_for(lambda: window.connected and bool(window.latest))
    yield window
    window.close()
    wait_for(lambda: not window.worker.isRunning())


def test_selecting_profile_does_not_apply_it(window):
    window.presets["ultra"].click()
    assert window.latest["active"] == "auto"


def test_apply_and_auto_buttons(window):
    window.presets["high"].click()
    window.apply_button.click()
    wait_for(lambda: window.latest.get("active") == "high")
    assert "→ AUTO" in window.active.text()
    window.auto_button.click()
    wait_for(lambda: window.latest.get("active") == "auto")


def test_ultra_is_automatic_performance_and_language_switches(window):
    window.presets["ultra"].click()
    window.apply_button.click()
    wait_for(lambda: window.latest.get("active") == "ultra")
    assert window.latest["thermal"] == "performance"
    assert window.latest["remaining_s"] is None
    window.language.setCurrentIndex(1)
    assert window.apply_button.text() == "Apply profile"


def test_demo_is_clearly_marked_and_no_manual_level_three_exists(window):
    assert "DEMO" in window.windowTitle()
    assert set(window.presets) == {"balanced", "cool", "quiet", "ultra", "low", "high"}
    assert window.duration.minimum() == 1 and window.duration.maximum() == 60
