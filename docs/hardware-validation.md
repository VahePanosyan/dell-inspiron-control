# Hardware validation

Date: 2026-11-21. Tested platform: Dell Inspiron 16 Plus 7630, board 006JN2 A00,
BIOS 1.30.0, Core i7-13620H, RTX 4060 Laptop GPU, Windows 11 x64.
This report is intentionally sanitized; serial numbers, service tags, ACPI tables,
machine paths and raw local diagnostics are not published.

## Higher manual fan state

`LegacyDiags.Execute` uses the documented community Dell SMM register format.
Nominal read command `0x04A3` returned the following for both fans:

| Fan state | Reported nominal RPM | Setter validation |
|---|---:|---|
| 1 | 2400 | Previously validated on both fans |
| 2 | 4000 | Validated on both fans |
| 3 | 6200 | First fan setter rejected with EAX `0x0000FFFF`; test stopped |

The bounded test first used state 2, then attempted state 3. An independent recovery
process was running. The BIOS rejected `0x01A3` with EBX `0x0300`. No state-3 command
was sent to the second fan after that failure. The test's finally block successfully
returned AUTO and restored the original Performance policy.

Reading a 6200 RPM nominal value was therefore insufficient to enable manual turbo.
This release exposes states 1/2 only. Ultra Performance uses automatic BIOS cooling.
Earlier automatic readings on this machine reached approximately 5200/4300 RPM.

## Built executable checks

The **packaged Windows executable**, not just Python source, passed:

* GUI demo test: select/apply low, high, Ultra, Balanced and AUTO; language switch;
  minimum-window geometry check at 980×770; orderly worker shutdown. Screenshot
  in the README is explicitly simulated demo telemetry.
* Opt-in live check: apply Ultra and read back Performance; timed manual high session;
  automatic timer expiry; deliberately withheld controller heartbeats; successful
  independent recovery after approximately five seconds.
* Live check final state: AUTO accepted, initial Performance thermal policy restored.

Unit and simulated GUI suite: **43 tests passed**. CI runs these tests and builds a
portable executable; CI does not claim to validate real Dell firmware.

## GPU power observations

In earlier 40-second CUDA measurements, after excluding the first ten seconds:

| Workload | Dell policy | Mean GPU power | Maximum GPU temperature |
|---|---|---:|---:|
| FP32 GPU load | Balanced | 63.64 W | 71 °C |
| FP32 GPU load | Performance | 69.81 W | 75 °C |
| FP16 GPU load | Performance | 68.41 W | 75 °C |
| FP16 + four CPU threads | Performance | 63.42 W | 77 °C |

NVIDIA's direct `-pl 70` request was rejected as unsupported, despite exit code zero.
The application does not issue that setter. Performance enables Dell's stock dynamic
behavior; 70 W is not guaranteed for arbitrary workloads. Specific 45–55 W game
scenarios were not measured, and background processes were not terminated.

## Scope

No raw EC writes, firmware flashing, driver/service changes, fan-stop, thermal-limit
bypass or persistent startup task was used. No hardware support is claimed for
an Inspiron 7830 or for other boards/BIOS versions on the basis of a similar name.
