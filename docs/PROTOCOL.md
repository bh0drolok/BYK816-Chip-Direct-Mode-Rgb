# Protocol notes (Rapoo V720 / BYK816, as reverse engineered)

Short reference. Background and evidence: [BYK816 Direct Mode Research Docs.md](BYK816%20Direct%20Mode%20Research%20Docs.md).
USB `24AE:4018`. Everything marked "new" exists **only in the patched firmware**.

## Direct colour command (new)

HID **feature report**, report ID 5, 6 bytes:

```
05 E0 idx R G B
```

| Byte | Meaning |
|---|---|
| `05` | report ID (vendor, 6-byte reports) |
| `E0` | command: set one key colour, RAM only |
| `idx` | `row * 22 + column` on the 6 x 22 grid, valid `0..131`; invalid or empty slots are ignored |
| `R G B` | 0-255 each, stored as given (v7 and later: no brightness scaling) |

- Writes the key's B/G/R bytes into the live buffer (XRAM `0x0386 + off + ch`) and, unless the key is lock-indicated, the LED array (XRAM `0x01D9 + off + ch`), with `off = T1*0x12 + T2*3` from the firmware key tables. Nothing is written to flash.
- Any other 6-byte report is handled exactly as stock.
- Only one HID collection accepts report 5 on Windows (usage page `0xFF00`, interface 1, one of three collections). Find it by sending the harmless probe `05 83 00 00 00 00` and keeping the path that succeeds.
- Keyboard must be in the painted/software mode for the colours to be visible.
- Safe rate: about 1600 reports/s on v9; about 400-800/s on v7/v8.

## Stock reports (for reference)

| Report | Size | Layout | Notes |
|---|---|---|---|
| 5 | 6 | `05 83 00 00 00 00` | sync/probe, harmless |
| 5 | 6 | `05 75`, `05 A5`, `05 5A`, `05 01` | other commands in the firmware chain, not documented here |
| 6 | 1032 | `06 type hi lo 40 00 00 00` + 0x400 bytes | type `09` = painting page write (**flash erase+program, do not stream**), type `03` = settings to external EEPROM |

Painting page (type `09`, address `AC00`): three planes of 0x84 bytes (blue, green, red), index = `row*22 + col`.

## Key index grid

See Appendix A of the research document. 104 valid indexes:
`0, 2-5, 7-17, 22-34, 36-57, 59-77, 79, 84, 85, 86, 88, 90-99, 102, 104, 106-112, 115, 118, 119, 120, 122, 125-128, 130`.
