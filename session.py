"""Serialized control state, independent of GUI and COM thread ownership."""
import time

from profiles import resolve_profile, verify_temperatures


class ControlSession:
    def __init__(self, ctrl, thermal, guard_factory, *, clock=time.monotonic):
        self.ctrl, self.thermal, self.guard_factory = ctrl, thermal, guard_factory
        self.clock = clock
        self.guard = None
        self.deadline = None
        self.level = None
        self.active = "auto"

    def auto(self):
        self.ctrl.auto()
        if self.guard:
            self.guard.stop()
            self.guard = None
        self.level = self.deadline = None
        self.active = "auto"

    def apply(self, profile_id: str, seconds: int):
        profile = resolve_profile(profile_id, seconds)
        if profile.level is not None:
            verify_temperatures(self.ctrl.status())
        self.auto()
        if profile.thermal:
            self.thermal.set_mode(profile.thermal)
        if profile.level is not None:
            self.guard = self.guard_factory(seconds)
            try:
                self.ctrl.manual()
                for fan in (0, 1):
                    self.ctrl.set_level(fan, profile.level)
                self.level = profile.level
                self.deadline = self.clock() + seconds
            except BaseException:
                self.auto()
                raise
        self.active = profile.id

    def tick(self) -> dict:
        status = self.ctrl.status()
        if self.level is not None:
            try:
                verify_temperatures(status)
                if self.clock() >= self.deadline:
                    self.auto()
                elif self.guard:
                    self.guard.pulse()
            except Exception:
                self.auto()
                raise
        status["active"] = self.active
        status["remaining_s"] = max(0, int(self.deadline - self.clock())) if self.deadline else None
        status["thermal"] = self.thermal.status()["current"]
        return status
