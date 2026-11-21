# Tested Dell ACPI-WMI transport. No raw EC or third-party kernel driver.
from __future__ import annotations
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import struct

class FanError(RuntimeError):
    """Firmware rejection, missing telemetry or failed restoration."""

def decode_register(raw: bytes, command: int) -> int:
    if len(raw) != 4:
        raise FanError("Invalid SMM register length")
    value = struct.unpack("<I", raw)[0]
    if value == command or value & 0xFFFF == 0xFFFF:
        raise FanError(f"BIOS rejected SMM command {command:#06x}: {value:#010x}")
    return value

def connect(namespace: str):
    import win32com.client
    return win32com.client.GetObject(
        "winmgmts:{impersonationLevel=impersonate,authenticationLevel=PktPrivacy}!\\\\.\\" + namespace
    )

def thermal_buffer(size: int, operation: int, setting: int = 0) -> bytes:
    if not 52 <= size <= 1048576:
        raise FanError(f"Invalid BFn buffer size {size}")
    data = bytearray(size)
    struct.pack_into("<HH4I", data, 0, 17, 19, operation, setting, 0, 0)
    struct.pack_into("<I", data, 20, 0x7FFFFFFF)
    return bytes(data)

class Thermal:
    MODES = {"balanced": 1, "cool": 2, "quiet": 4, "performance": 8}

    def __init__(self):
        self.wmi = connect(r"root\wmi")
        data = bytes(next(iter(self.wmi.InstancesOf("WMI_Query"))).QDATA.Bytes)
        if len(data) < 16 or data[:8] != b"DELL WMI":
            raise FanError("Invalid Dell QDATA signature")
        self.size = struct.unpack_from("<I", data, 12)[0]
        self.bfn = next(iter(self.wmi.InstancesOf("BFn")))

    def call(self, operation: int, setting: int = 0) -> tuple[int, int, int, int]:
        bdat = self.wmi.Get("BDat").SpawnInstance_()
        bdat.Bytes = tuple(thermal_buffer(self.size, operation, setting))
        args = self.bfn.Methods_("DoBFn").InParameters.SpawnInstance_()
        args.Data = bdat
        raw = bytes(self.bfn.ExecMethod_("DoBFn", args).Data.Bytes)
        if len(raw) < 36 or raw[:4] != struct.pack("<HH", 17, 19):
            raise FanError("Invalid thermal response")
        result = struct.unpack_from("<iIII", raw, 20)
        if result[0] != 0:
            raise FanError(f"BIOS rejected thermal command: status {result[0]}")
        return result

    def status(self) -> dict:
        _, supported, current, _ = self.call(0)
        return {"supported_mask": supported, "current_raw": current,
                "supported": [n for n, code in self.MODES.items() if supported & code],
                "current": next((n for n, code in self.MODES.items() if current & 255 == code), "unknown")}

    def set_mode(self, name: str) -> dict:
        code = self.MODES[name]
        before = self.status()
        if not before["supported_mask"] & code:
            raise FanError(f"Thermal mode {name} unsupported")
        # Preserve the existing Active Acoustic Controller setting (Dell libsmbios).
        aac = (before["current_raw"] >> 16) & 255
        self.call(1, (aac << 8) | code)
        after = self.status()
        if after["current"] != name:
            raise FanError(f"Thermal change not verified: {after}")
        return after

class Controller:
    def __init__(self):
        cim = connect(r"root\cimv2")
        model = next(iter(cim.InstancesOf("Win32_ComputerSystem")))
        board = next(iter(cim.InstancesOf("Win32_BaseBoard")))
        if (model.Manufacturer != "Dell Inc." or model.Model != "Inspiron 16 Plus 7630"
                or board.Product != "006JN2"):
            raise FanError(f"Untested platform: {model.Model}, board {board.Product}")
        self.wmi = connect(r"root\dcim\sysman\diagnostics")
        self.instance = next(iter(self.wmi.InstancesOf("LegacyDiags")))
        self.ddv = None
        signature = self.call(0xFEA3)
        if (signature["Eax"], signature["Edx"]) != (0x44494147, 0x44454C4C):
            raise FanError("Invalid Dell SMM signature")

    def call(self, command: int, argument: int = 0) -> dict[str, int]:
        args = self.instance.Methods_("Execute").InParameters.SpawnInstance_()
        for reg, value in (("Eax", command), ("Ebx", argument), ("Ecx", 0), ("Edx", 0)):
            setattr(args, reg + "Len", 4)
            setattr(args, reg + "Val", tuple(struct.pack("<I", value)))
        output = self.instance.ExecMethod_("Execute", args)
        result = {}
        for reg in ("Eax", "Ebx", "Ecx", "Edx"):
            raw = bytes(getattr(output, reg + "Val"))
            if len(raw) != 4:
                raise FanError("Invalid SMM register length")
            result[reg] = struct.unpack("<I", raw)[0]
        decode_register(bytes(output.EaxVal), command)
        return result

    def auto(self):
        if self.call(0x31A3)["Eax"] != 0:
            raise FanError("AUTO command did not return success")

    def manual(self):
        if self.call(0x30A3)["Eax"] != 0:
            raise FanError("MANUAL command did not return success")

    def set_level(self, fan: int, level: int):
        if fan not in (0, 1) or level not in (1, 2):
            raise ValueError("Only fans 0/1 and tested levels 1/2 are supported")
        if self.call(0x1A3, fan | (level << 8))["Eax"] != 0:
            raise FanError("Fan level command did not return success")

    def status(self) -> dict:
        temperatures = [self.call(0x10A3, sensor)["Eax"] & 0xFF for sensor in (0, 1)]
        if any(not 1 <= x <= 125 for x in temperatures):
            raise FanError(f"Invalid thermal sensor response: {temperatures}")
        return {
            "model": "Inspiron 16 Plus 7630", "board": "006JN2",
            "fan_rpm": [self.call(0x2A3, f)["Eax"] & 0xFFFF for f in (0, 1)],
            "fan_level": [self.call(0xA3, f)["Eax"] & 0xFF for f in (0, 1)],
            "temperatures_c": temperatures,
        }
