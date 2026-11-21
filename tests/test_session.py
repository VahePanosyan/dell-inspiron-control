from unittest.mock import Mock

import pytest

from session import ControlSession


def setup_session():
    ctrl, thermal, guard = Mock(), Mock(), Mock()
    thermal.status.return_value = {"current": "balanced"}
    ctrl.status.return_value = {"fan_rpm": [2500, 2500], "temperatures_c": [70, 60]}
    clock = Mock(return_value=100)
    session = ControlSession(ctrl, thermal, lambda _: guard, clock=clock)
    return session, ctrl, thermal, guard, clock


def test_manual_starts_guard_before_disabling_auto():
    session, ctrl, _, guard, _ = setup_session()
    order = []
    session.guard_factory = lambda seconds: order.append("guard") or guard
    ctrl.manual.side_effect = lambda: order.append("manual")
    session.apply("high", 60)
    assert order == ["guard", "manual"]
    assert session.deadline == 160
    assert ctrl.set_level.call_args_list[0].args == (0, 2)


def test_manual_expiry_restores_auto_and_stops_guard():
    session, ctrl, _, guard, clock = setup_session()
    session.apply("low", 60)
    clock.return_value = 161
    session.tick()
    assert session.deadline is None
    assert session.active == "auto"
    guard.stop.assert_called_once()
    assert ctrl.auto.call_count == 2


def test_partial_set_failure_restores_auto():
    session, ctrl, _, guard, _ = setup_session()
    ctrl.set_level.side_effect = RuntimeError("setter failed")
    with pytest.raises(RuntimeError, match="setter failed"):
        session.apply("high", 60)
    guard.stop.assert_called_once()
    assert session.level is None
    assert ctrl.auto.call_count == 2


def test_failed_auto_keeps_independent_guard_running():
    session, ctrl, _, guard, _ = setup_session()
    session.apply("low", 60)
    ctrl.auto.side_effect = RuntimeError("AUTO failed")
    with pytest.raises(RuntimeError):
        session.auto()
    guard.stop.assert_not_called()


def test_hot_sensor_aborts_an_active_session():
    session, ctrl, _, guard, _ = setup_session()
    session.apply("high", 60)
    ctrl.status.return_value = {"temperatures_c": [90, 60], "fan_rpm": [4000, 4000]}
    with pytest.raises(RuntimeError, match="90"):
        session.tick()
    guard.stop.assert_called_once()
    assert session.level is None


def test_ultra_uses_performance_with_automatic_fans():
    session, ctrl, thermal, _, _ = setup_session()
    session.apply("ultra", 300)
    thermal.set_mode.assert_called_once_with("performance")
    ctrl.manual.assert_not_called()
    assert session.level is None


def test_rejected_profile_is_not_reported_as_applied():
    session, _, thermal, _, _ = setup_session()
    thermal.set_mode.side_effect = RuntimeError("rejected")
    with pytest.raises(RuntimeError):
        session.apply("ultra", 300)
    assert session.active == "auto"


def test_unknown_command_has_no_hardware_effect():
    session, ctrl, thermal, _, _ = setup_session()
    with pytest.raises(ValueError):
        session.apply("untrusted", 60)
    ctrl.auto.assert_not_called()
    thermal.set_mode.assert_not_called()


def test_guard_failure_returns_auto():
    session, ctrl, _, guard, _ = setup_session()
    session.apply("high", 60)
    guard.pulse.side_effect = RuntimeError("guard stopped")
    with pytest.raises(RuntimeError, match="guard stopped"):
        session.tick()
    assert ctrl.auto.call_count == 2
    guard.stop.assert_called_once()
