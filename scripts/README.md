# Scripts

> **These scripts are a guideline, not exact or supported tools.** They are the scripts that were actually used
> during the research on one keyboard (Rapoo V720, BYK816), cleaned up so they run without the original machine's
> paths. Expect to adjust offsets, paths and assumptions for any other board or firmware revision.
> **No firmware images are included.** The firmware builders need a dump of *your own* keyboard's flash, which you
> must take yourself. Nothing here writes to a keyboard's flash; flashing is done with a separate tool (sinowisp).
> Licence: MIT (see `LICENSE`).

## Firmware patch chain (needs your own stock dump, `stock.bin` or `.hex`)

| Script | What it does |
|---|---|
| `build_v6.py <stock> <out.bin>` | Adds the direct-colour command `05 E0 idx R G B` in an unused (all-zero) flash area; hook at `0x5358` (v6 also scales by brightness) |
| `build_v7.py <stock> <out.hex>` | v6 with brightness scaling removed (2 bytes changed). Hardware-proven base |
| `build_v8.py <stock> <out.hex>` | v7 + release guard (cures stuck keys) |
| `build_v9.py <stock> <out.hex>` | v7 + guard with held-key resend (cures most missed presses). Latest |
| `test_v7.py`, `test_v8.py`, `test_v9.py <stock>` | Run the patched code in the 8051 emulator against the stock code (behaviour, stack, side effects) |
| `sim51.py`, `d51.py` | Small 8051 emulator and disassembler used by the tests |
| `boot_sim.py`, `tick_sim.py` | Boot the firmware in the emulator / drive main-loop ticks (used to find the LED buffers and flags) |
| `fwtools.py`, `ihex2bin.py` | Intel HEX / binary helpers |

Example: `python build_v9.py stock.bin v9.hex` then `python test_v9.py stock.bin`.
The builders refuse to run if the bytes they expect are not where they expect them (different firmware).

## Talking to the keyboard (Python, `pip install hidapi`)

`kb.py` (HID path helper), `rt4.py` (static / rainbow / benchmark sender), `bridge.py` (Art-Net-style bridge),
`viz.py` (audio visualiser; needs `numpy` and `pyaudiowpatch`). These were the first real-time proofs before the
OpenRGB driver existed. They only make sense with a patched firmware.

## `klmtest/`

`layout_dump.cpp` prints OpenRGB's `KeyboardLayoutManager` ANSI-full matrix and key names (used to build the
hardware-index to OpenRGB-key map). It needs OpenRGB's source tree to compile.

## `history/`

Earlier attempts (v1-v5: RAM-frame and streaming variants), their tests and small experiments, kept for the record
of what was tried. They are not maintained; several take a base-directory argument and expect the old image names.
