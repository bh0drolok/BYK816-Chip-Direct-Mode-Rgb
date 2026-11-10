# OpenRGB controller for the Rapoo V720 (patched firmware, direct mode)

Native OpenRGB driver for a Rapoo V720 keyboard (VID `0x24AE`, PID `0x4018`, BYK816 chip) running a firmware that
has the **direct-colour command** added (see [`../docs/`](../docs/)). With that firmware the keyboard appears in
OpenRGB as a normal ANSI-104 keyboard with per-key colour, and every OpenRGB effect, the Effects plugin and the
audio visualiser work in real time.

> **This driver does nothing useful on stock firmware.** The command it sends (`05 E0 idx R G B`) only exists
> in the patched firmware. On a stock keyboard the reports are ignored or may trigger unrelated vendor
> functions. Read the research document first, and only flash a patched firmware if you accept the risks described there.

## Files

| File | Purpose |
|---|---|
| `RapooV720ControllerDetect.cpp` | HID detector registration (VID/PID, interface and usage page) |
| `RapooV720Controller.h/.cpp` | Low-level device class: sends one key colour per 6-byte feature report, paced to a report-rate limit |
| `RGBController_RapooV720.h/.cpp` | OpenRGB device: Direct mode, `KeyboardLayoutManager` ANSI layout, and a **sender thread** that always converges on the latest colours without ever blocking OpenRGB |

## How it works (short)

* One key per report: feature report `05 E0 idx R G B`, `idx = row * 22 + column` (6 rows x 22 columns, 104 real keys).
* OpenRGB's update call only records the wanted colours (rounded to steps of 4) and wakes a sender thread.
* The sender thread sends every key whose colour differs from what the keyboard shows, biggest change first,
  finishing each pass before taking the newest colours. Frames that arrive meanwhile are skipped, so the **last colour always wins**
  and effects look coherent.
* Reports are paced to a limit (default **1600 per second**). The keyboard handles key presses in the same
  main loop that receives the reports, so unpaced sending makes it miss presses.

## The report-rate limit

| Firmware | Suggested rate |
|---|---|
| v9 patch (held-key resend) | 1600/s default; 2000/s showed no missed keys in short tests |
| v8 patch (release guard) | about 400-800/s |
| v7 or older | about 400-800/s, expect occasional stuck or missed keys |

Change it without rebuilding with the environment variable `RAPOO_V720_MAX_RATE` (allowed range 50-2000),
set before OpenRGB starts:

```powershell
$env:RAPOO_V720_MAX_RATE = 800     # this PowerShell window only
setx RAPOO_V720_MAX_RATE 800       # permanent; restart OpenRGB completely afterwards
```

## Building

Copy the `RapooV720Controller` folder into `Controllers/` of an OpenRGB source tree (the project files pick up controller
sources by wildcard, no `.pro` edit is needed) and build OpenRGB as usual. On Windows this was built with
Visual Studio 2022 Build Tools, the Windows SDK and Qt 6.8.3 using `scripts\build-windows.bat 6.8.3 2022 64`
on OpenRGB's `master` at the time (OpenRGB 1.1 development, SDK protocol 6, plugin API 5).

## Things worth knowing if you read or reuse the code

* `ToRGBColor(r, g, b)` is a **macro without parentheses around its arguments**. `ToRGBColor(x & 0xFC, ...)` silently
  zeroes the green and blue channels. Compute the rounded channels in variables first (the code does).
* `SetKey()` waits for its turn, so it must only be called from the sender thread, never from OpenRGB's update path
  (waiting there makes OpenRGB and its effect preview lag).
* The layout comes from `KeyboardLayoutManager` (ANSI full). Hardware key names that differ from the library's names are
  mapped in `RapooV720KeyIndex()` (for example the key the library calls "Right Fn" is the Windows key on this board).
* The four extra keys above the numpad (Fn, Mute, Win Lock, M) are not in the 104-key layout and are not driven by this driver.

## Licence

GPL-2.0-or-later, the same as OpenRGB (see `LICENSE`, which is OpenRGB's licence text). The files carry the same SPDX line
as OpenRGB's own sources.
