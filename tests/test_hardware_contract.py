import struct
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hardware import Controller, FanError, Thermal, decode_register, thermal_buffer


@pytest.mark.parametrize("value", [0x1A3, 0xFFFF, 0xFFFFFFFF])
def test_smm_unsupported_response_cannot_be_success(value):
    with pytest.raises(FanError):
        decode_register(struct.pack("<I", value), 0x1A3)


def test_truncated_smm_response_is_rejected():
    with pytest.raises(FanError):
        decode_register(b"\0", 0x1A3)


def test_bfn_has_class_at_zero_and_status_at_twenty():
    raw = thermal_buffer(32768, 1, 8)
    assert len(raw) == 32768
    assert struct.unpack_from("<HH4I", raw) == (17, 19, 1, 8, 0, 0)
    assert struct.unpack_from("<I", raw, 20)[0] == 0x7FFFFFFF


@pytest.mark.parametrize("size", [0, 36, 1048577])
def test_untrusted_buffer_size_is_rejected(size):
    with pytest.raises(FanError):
        thermal_buffer(size, 0)


@pytest.mark.parametrize("model,board", [("Inspiron 16 Plus 7830", "006JN2"),
                                        ("Inspiron 16 Plus 7630", "OTHER")])
def test_unverified_hardware_never_opens_the_write_transport(monkeypatch, model, board):
    cim = Mock()
    cim.InstancesOf.side_effect = [[SimpleNamespace(Manufacturer="Dell Inc.", Model=model)],
                                  [SimpleNamespace(Product=board)]]
    connect = Mock(return_value=cim)
    monkeypatch.setattr("hardware.connect", connect)
    with pytest.raises(FanError, match="Untested platform"):
        Controller()
    connect.assert_called_once_with(r"root\cimv2")


@pytest.mark.parametrize("level", [0, 3, 4, 255])
def test_rejected_or_stop_levels_are_not_writable(level):
    ctrl = Controller.__new__(Controller)
    ctrl.call = Mock()
    with pytest.raises(ValueError):
        ctrl.set_level(0, level)
    ctrl.call.assert_not_called()


def test_thermal_set_preserves_acoustic_setting_and_reads_back():
    thermal = Thermal.__new__(Thermal)
    thermal.status = Mock(side_effect=[{"supported_mask": 15, "current_raw": 0x10001},
                                       {"current": "performance"}])
    thermal.call = Mock()
    thermal.set_mode("performance")
    thermal.call.assert_called_once_with(1, 0x108)


def test_thermal_success_status_still_requires_correct_readback():
    thermal = Thermal.__new__(Thermal)
    thermal.status = Mock(side_effect=[{"supported_mask": 15, "current_raw": 1},
                                       {"current": "balanced"}])
    thermal.call = Mock()
    with pytest.raises(FanError, match="not verified"):
        thermal.set_mode("performance")
