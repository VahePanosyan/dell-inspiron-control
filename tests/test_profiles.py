import pytest

from profiles import PROFILES, resolve_profile, verify_temperatures


def test_ultra_is_verified_automatic_performance_not_rejected_level_three():
    ultra = resolve_profile("ultra", 300)
    assert ultra.thermal == "performance"
    assert ultra.level is None
    assert all(p.level in (None, 1, 2) for p in PROFILES.values())


@pytest.mark.parametrize("seconds", [0, -1, 3601, True, "60", 1.5])
def test_bad_duration_is_rejected(seconds):
    with pytest.raises(ValueError):
        resolve_profile("high", seconds)


def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError):
        resolve_profile("raw-command", 60)


@pytest.mark.parametrize("values", [[], [60], [60, 90], [0, 50], [float("nan"), 50]])
def test_bad_temperatures_stop_manual(values):
    with pytest.raises(RuntimeError):
        verify_temperatures({"temperatures_c": values})


def test_normal_temperatures_are_accepted():
    verify_temperatures({"temperatures_c": [80, 65]})
