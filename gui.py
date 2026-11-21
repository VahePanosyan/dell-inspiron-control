"""Native Qt dashboard. Hardware work is isolated in HardwareService."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QKeySequence, QShortcut, QIcon
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QMainWindow, QPlainTextEdit, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)

from profiles import PROFILES
from service import HardwareService

VERSION = "0.1.0"
COPY = {
    "ru": {"title": "Питание и охлаждение", "subtitle": "Штатные профили Dell. Управление на вашем устройстве.",
           "connecting": "Подключение к контроллеру…", "connected": "Подключено · управление доступно",
           "unsupported": "Управление недоступно — проверьте сообщение ниже",
           "fan1": "Вентилятор 1", "fan2": "Вентилятор 2", "power": "Мощность GPU",
           "profiles": "Профили", "duration": "Таймер ручного режима", "minutes": " мин",
           "apply": "Применить профиль", "auto": "Вернуть AUTO  ·  Esc",
           "log": "События", "footer": "При выходе вентиляторы вернутся в AUTO. Тепловой профиль сохраняется.",
           "compat": "Проверено: Inspiron 16 Plus 7630\nПлата 006JN2 · Windows x64",
           "demo": "ДЕМОРЕЖИМ — данные смоделированы, оборудование не изменяется",
           "closing": "Возврат вентиляторов в AUTO…", "active": "Активно", "sensor": "Датчик",
           "limit": "Лимит", "thermal": "Профиль Dell", "na": "нет данных",
           "balanced": "Ежедневная работа и автоматическое охлаждение.",
           "cool": "Штатный профиль с более прохладной поверхностью.",
           "quiet": "Штатный профиль для более тихой работы.",
           "ultra": "Dell Performance + AUTO. BIOS может поднимать RPM выше 4000.",
           "low": "Ручной уровень 1: около 2400 RPM, по таймеру.",
           "high": "Ручной уровень 2: около 4000 RPM, по таймеру.",
           "turbo_note": "Ручной уровень 3 отклонён BIOS. Ultra использует штатный Performance + AUTO."},
    "en": {"title": "Power & cooling", "subtitle": "Dell thermal profiles. Local control of your device.",
           "connecting": "Connecting to controller…", "connected": "Connected · control available",
           "unsupported": "Control unavailable — see the message below",
           "fan1": "Fan 1", "fan2": "Fan 2", "power": "GPU power", "profiles": "Profiles",
           "duration": "Manual fan timer", "minutes": " min", "apply": "Apply profile",
           "auto": "Restore AUTO  ·  Esc", "log": "Activity",
           "footer": "Closing restores automatic fans. The selected thermal profile stays active.",
           "compat": "Tested: Inspiron 16 Plus 7630\nBoard 006JN2 · Windows x64",
           "demo": "DEMO — simulated telemetry; hardware is never modified",
           "closing": "Restoring automatic fan control…", "active": "Active", "sensor": "Sensor",
           "limit": "Limit", "thermal": "Dell profile", "na": "unavailable",
           "balanced": "Everyday performance and automatic cooling.",
           "cool": "Dell's cooler-surface thermal policy.",
           "quiet": "Dell's quieter thermal policy.",
           "ultra": "Dell Performance + AUTO. BIOS can select speeds above 4000 RPM.",
           "low": "Manual level 1: nominal 2400 RPM, with a timer.",
           "high": "Manual level 2: nominal 4000 RPM, with a timer.",
           "turbo_note": "BIOS rejected manual level 3. Ultra uses Dell Performance + AUTO."},
}

STYLE = """
QMainWindow, QWidget#main { background: #0e131a; color: #e5edf6; }
QWidget { color: #e5edf6; font-family: 'Segoe UI'; font-size: 13px; }
QFrame#sidebar { background: #121b25; border-right: 1px solid #263442; }
QFrame#metric { background: #17212d; border: 1px solid #283746; border-radius: 12px; }
QLabel#muted { color: #a2b1c2; }
QLabel#section { font-size: 15px; font-weight: 600; }
QLabel#hero { font-size: 28px; font-weight: 650; }
QLabel#metricValue { font-size: 30px; font-weight: 650; }
QPushButton { background: #192531; border: 1px solid #344454; border-radius: 9px; padding: 11px 15px; }
QPushButton:hover { background: #203344; border-color: #66b9d1; }
QPushButton:focus { border: 2px solid #65d7ec; }
QPushButton:disabled { color: #778695; background: #16202a; border-color: #28333f; }
QPushButton[role="preset"] { text-align: left; padding: 0; }
QPushButton[role="preset"]:checked { background: #173c37; border: 2px solid #50d6b1; }
QPushButton#applyButton { background: #37c69c; color: #071d1a; font-weight: 700; border: none; }
QPushButton#applyButton:hover { background: #60deb8; }
QPushButton#applyButton:disabled { background: #263a39; color: #8ba6a0; }
QPushButton#autoButton { border: 1px solid #53cbb3; color: #9df4dc; }
QComboBox, QSpinBox { background: #17212d; border: 1px solid #3d5062; border-radius: 6px; padding: 6px; }
QComboBox QAbstractItemView { background: #17212d; selection-background-color: #265b51; }
QPlainTextEdit { background: #111b25; color: #b8c7d7; border: 1px solid #283746; border-radius: 8px; padding: 6px; }
QToolTip { color: #e5edf6; background: #213140; border: 1px solid #4c647a; }
"""


class MainWindow(QMainWindow):
    def __init__(self, *, demo=False):
        super().__init__()
        self.demo = demo
        self.connected = False
        self.closing = False
        self.latest = {}
        self.last_problem = ""
        self.lang = "ru"
        self.translated = []
        self.setWindowTitle("Dell Inspiron Control" + (" — DEMO" if demo else ""))
        self.resize(1100, 810)
        self.setMinimumSize(980, 770)
        self.setStyleSheet(STYLE)
        self._build()
        self.worker = HardwareService(demo=demo)
        self.worker.ready.connect(self._ready)
        self.worker.snapshot.connect(self._snapshot)
        self.worker.event.connect(self._event)
        self.worker.problem.connect(self._problem)
        self.worker.finished.connect(self._finished)
        self.worker.start()
        self.shortcut = QShortcut(QKeySequence("Esc"), self)
        self.shortcut.activated.connect(self.restore_auto)
        self._translate()

    def tr_label(self, key, *, name="", wrap=False):
        label = QLabel()
        label.setWordWrap(wrap)
        if name:
            label.setObjectName(name)
        self.translated.append((label, key))
        return label

    def _build(self):
        main = QWidget(objectName="main")
        self.setCentralWidget(main)
        row = QHBoxLayout(main)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        sidebar = QFrame(objectName="sidebar")
        sidebar.setFixedWidth(205)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(24, 30, 22, 24)
        brand = QLabel("◉  INSPIRON\n    CONTROL")
        brand.setStyleSheet("font-size: 20px; font-weight: 700; color: #68e1bf;")
        nav.addWidget(brand)
        model = QLabel("16 PLUS 7630")
        model.setStyleSheet("color: #9aaec3; letter-spacing: 2px; padding-top: 9px;")
        nav.addWidget(model)
        nav.addSpacing(35)
        nav.addWidget(QLabel("●  DASHBOARD"))
        nav.addWidget(QLabel("    PROFILES / TELEMETRY", objectName="muted"))
        nav.addStretch()
        nav.addWidget(self.tr_label("compat", name="muted", wrap=True))
        nav.addSpacing(20)
        nav.addWidget(QLabel(f"v{VERSION}  ·  LOCAL / WMI", objectName="muted"))
        row.addWidget(sidebar)
        content = QVBoxLayout()
        content.setContentsMargins(26, 23, 26, 18)
        content.setSpacing(13)
        row.addLayout(content, 1)
        heading = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(3)
        titles.addWidget(self.tr_label("title", name="hero"))
        titles.addWidget(self.tr_label("subtitle", name="muted"))
        heading.addLayout(titles, 1)
        self.language = QComboBox(objectName="languageCombo")
        self.language.setAccessibleName("Language")
        self.language.addItems(["Русский", "English"])
        self.language.currentIndexChanged.connect(self._language_changed)
        heading.addWidget(self.language, 0, Qt.AlignmentFlag.AlignTop)
        content.addLayout(heading)
        self.banner = QLabel(objectName="connectionStatus")
        self.banner.setWordWrap(True)
        self.banner.setMinimumHeight(22)
        content.addWidget(self.banner)
        if self.demo:
            demo_label = self.tr_label("demo", wrap=True)
            demo_label.setStyleSheet("color: #ffc57a; font-weight: 600;")
            content.addWidget(demo_label)
        metrics = QHBoxLayout()
        self.metric_values, self.metric_details = [], []
        for key in ("fan1", "fan2", "power"):
            card = QFrame(objectName="metric")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(17, 13, 17, 13)
            layout.setSpacing(2)
            layout.addWidget(self.tr_label(key, name="muted"))
            value = QLabel("—", objectName="metricValue")
            value.setAccessibleName(key)
            layout.addWidget(value)
            detail = QLabel("—", objectName="muted")
            layout.addWidget(detail)
            self.metric_values.append(value)
            self.metric_details.append(detail)
            metrics.addWidget(card, 1)
        content.addLayout(metrics)
        profile_heading = QHBoxLayout()
        profile_heading.addWidget(self.tr_label("profiles", name="section"))
        profile_heading.addStretch()
        self.active = QLabel(objectName="activeProfile")
        self.active.setStyleSheet("color: #75e4c2;")
        profile_heading.addWidget(self.active)
        content.addLayout(profile_heading)
        grid = QGridLayout()
        grid.setSpacing(10)
        self.group = QButtonGroup(self)
        self.presets = {}
        for index, profile_id in enumerate(("balanced", "cool", "quiet", "ultra", "low", "high")):
            profile = PROFILES[profile_id]
            button = QPushButton(objectName="preset_" + profile_id)
            button.setProperty("role", "preset")
            button.setProperty("profile_id", profile_id)
            button.setAccessibleName(profile_id)
            button.setCheckable(True)
            button.setMinimumHeight(98)
            button.setEnabled(False)
            self.group.addButton(button)
            layout = QVBoxLayout(button)
            layout.setContentsMargins(14, 10, 14, 10)
            layout.setSpacing(3)
            title = QLabel(profile.name)
            title.setStyleSheet("font-weight: 650; font-size: 14px;")
            title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(title)
            description = self.tr_label(profile_id, name="muted", wrap=True)
            description.setStyleSheet("font-size: 12px; color: #b5c5d4;")
            description.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(description, 1)
            grid.addWidget(button, index // 3, index % 3)
            self.presets[profile_id] = button
        self.presets["balanced"].setChecked(True)
        content.addLayout(grid)
        note = self.tr_label("turbo_note", name="muted", wrap=True)
        note.setStyleSheet("font-size: 11px; color: #a8b9c8;")
        content.addWidget(note)
        actions = QHBoxLayout()
        duration_box = QVBoxLayout()
        duration_box.setSpacing(3)
        duration_box.addWidget(self.tr_label("duration", name="muted"))
        self.duration = QSpinBox(objectName="durationSpin")
        self.duration.setAccessibleName("Manual duration")
        self.duration.setRange(1, 60)
        self.duration.setValue(5)
        duration_box.addWidget(self.duration)
        actions.addLayout(duration_box)
        actions.addStretch()
        self.apply_button = QPushButton(objectName="applyButton")
        self.apply_button.setAccessibleName("Apply profile")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_selected)
        actions.addWidget(self.apply_button, 0, Qt.AlignmentFlag.AlignBottom)
        self.auto_button = QPushButton(objectName="autoButton")
        self.auto_button.setAccessibleName("Restore AUTO")
        self.auto_button.setEnabled(False)
        self.auto_button.clicked.connect(self.restore_auto)
        actions.addWidget(self.auto_button, 0, Qt.AlignmentFlag.AlignBottom)
        content.addLayout(actions)
        self.current = QLabel(objectName="firmwareProfile")
        self.current.setWordWrap(True)
        content.addWidget(self.current)
        content.addWidget(self.tr_label("log", name="section"))
        self.log = QPlainTextEdit(objectName="activityLog")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(250)
        self.log.setFixedHeight(75)
        content.addWidget(self.log)
        content.addWidget(self.tr_label("footer", name="muted", wrap=True))
        content.addStretch()

    def _language_changed(self, index):
        self.lang = "en" if index else "ru"
        self._translate()

    def _translate(self):
        text = COPY[self.lang]
        for label, key in self.translated:
            label.setText(text[key])
        self.apply_button.setText(text["apply"])
        self.auto_button.setText(text["auto"])
        self.duration.setSuffix(text["minutes"])
        self.banner.setText(self.last_problem or text["connected" if self.connected else "connecting"])
        if self.latest:
            self._snapshot(self.latest)

    def _ready(self, connected):
        self.connected = connected
        self.banner.setText(COPY[self.lang]["connected" if connected else "unsupported"])
        self.banner.setStyleSheet("color: #75dfbd;" if connected else "color: #ffa2a2;")
        self.apply_button.setEnabled(connected)
        self.auto_button.setEnabled(connected)
        for button in self.presets.values():
            button.setEnabled(connected)

    def _snapshot(self, status):
        self.latest = status
        text = COPY[self.lang]
        rpm, temperatures = status["fan_rpm"], status["temperatures_c"]
        for i in (0, 1):
            self.metric_values[i].setText(f"{rpm[i]:,} <span style='font-size:13px;color:#a8bbc9'>RPM</span>")
            self.metric_details[i].setText(f"{text['sensor']} {i}  ·  {temperatures[i]} °C")
        gpu = status.get("gpu", {})
        self.metric_values[2].setText(f"{gpu['power_w']:.1f} <span style='font-size:15px;color:#a8bbc9'>W</span>" if gpu else "—")
        self.metric_details[2].setText(f"{gpu['temperature_c']} °C  ·  {text['limit']} {gpu['limit_w']:.0f} W" if gpu else text["na"])
        name = PROFILES[status["active"]].name
        remaining = status.get("remaining_s")
        if remaining is not None:
            name += f"  ·  {remaining // 60:02d}:{remaining % 60:02d} → AUTO"
        self.active.setText(f"{text['active']}: {name}")
        self.current.setText(f"{text['thermal']}: {status['thermal']}")
        if not self.closing:
            self.apply_button.setEnabled(self.connected)

    def _event(self, message):
        if message.startswith(("Applied:", "DEMO: applied")):
            self.last_problem = ""
            self.banner.setText(COPY[self.lang]["connected"])
            self.banner.setStyleSheet("color: #75dfbd;")
        self.log.appendPlainText(time.strftime("%H:%M:%S") + "  " + message)

    def _problem(self, message):
        self.last_problem = message
        self.banner.setText(message)
        self.banner.setStyleSheet("color: #ffad9f;")
        self._event("ERROR: " + message)
        self.apply_button.setEnabled(self.connected and not self.closing)

    def apply_selected(self):
        if not self.connected or self.closing:
            return
        selected = self.group.checkedButton().property("profile_id")
        self.apply_button.setEnabled(False)
        self.worker.submit(selected, self.duration.value() * 60)

    def restore_auto(self):
        if self.connected and not self.closing:
            self.worker.submit("auto")

    def closeEvent(self, event):
        if not self.worker.isRunning():
            event.accept()
            return
        event.ignore()
        if not self.closing:
            self.closing = True
            self._ready(False)
            self.banner.setText(COPY[self.lang]["closing"])
            self.worker.submit("shutdown")

    def _finished(self):
        if self.closing:
            self.close()
