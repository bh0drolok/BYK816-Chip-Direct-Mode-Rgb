# Firmware patches v6 - v9 (Rapoo V720 firmware, one specific revision)

These are the exact edits made on the research keyboard's firmware. **Addresses are specific to that firmware revision**
(stock dump MD5 `5bdf8220d1c3b068b3d265106d337ec2`, two reads matched). No images are published: build your own from your own dump with
`scripts/build_v7.py` / `build_v8.py` / `build_v9.py` (see `scripts/README.md`) and compare hashes. Only the app region
`0x0000-0xEFFF` is ever flashed; the boot loader at `0xF000+` is untouched.

| Version | Change vs previous | Bytes differing from stock | SHA-256 of the firmware-only hex (16-byte records, CRLF) |
|---|---|---|---|
| v6 | adds `05 E0 idx R G B`, brightness-scaled | 314 | `67d1be6b30361ae24ee167ff8223e4ec3519c35f697b9199cc58da05fd1645b6` |
| v7 | v6 without brightness scaling (2 bytes at `0xA500`: `FD 7C` -> `FF 22`) | 314 | `88c99b84f75eb9a2882c7e8ac8d5948bc8bbcb9a1a7bdbdd9deafb7957fd9ac3` |
| v8 | v7 + release guard | 314 + 54 | `d8f7cad56a002c5f188184a38afcb33eb39426b73d7e1a3fab86af7cfc55e93e` |
| v9 | v7 + guard with held-key resend | 314 + 75 | `a8685808b89ea5a351411a7309408f0d9fb1f1e77436d7922f85bab05c937f41` |

(v8 and v9 each differ from **v7** by 54 and 75 bytes respectively; they are alternatives, not stacked.)

## v6 / v7 - direct colour command

Hook: `0x5358  78 04 E2 -> 02 A5 19` (LJMP into the cave). Cave `0xA500-0xA63D` (all zero in stock). The annotated listing is
in section 10.3 of the research document. Scratch XRAM `0x0130-0x0135`.

## v8 / v9 - key-report guard

Call site: `0x5D9D  LCALL 8DAF` becomes `LCALL A640` (bytes `0x5D9E-0x5D9F`: `8D AF -> A6 40`). The guard runs once per keyboard-report
tick right before the 8-byte sender and ends by jumping to the original sender.

Flags and buffers used: IRAM `0x92-0xA7` (22 raw matrix columns, `FF` = no key), `4Fh` (10 ms counter), `53h` (1 ms counter),
`23h.0` (8-byte report pending), `27h.6` (NKRO report pending), `0x6C-0x73` (8-byte report buffer), `0x7E-0x8D` (NKRO buffer).
Clobbers only `R0`, `R7`, `A`, carry; +2 stack bytes.

### v9 guard (73 bytes at 0xA640)

```
A640: 78 92      MOV   R0,#92h          ; scan the 22 raw matrix columns
A642: 7f 16      MOV   R7,#16h
A644: e6         MOV   A,@R0
A645: b4 ff 2b   CJNE  A,#FFh,A673h     ; a key is down -> "held" branch
A648: 08         INC   R0
A649: df f9      DJNZ  R7,A644h
A64B: e5 4f      MOV   A,4Fh            ; idle: about every 160 ms ...
A64D: 54 0f      ANL   A,#0Fh
A64F: 70 35      JNZ   A686h
A651: e5 53      MOV   A,53h            ; ... at the start of a ms window
A653: c3         CLR   C
A654: 94 02      SUBB  A,#02h
A656: 50 2e      JNC   A686h
A658: 20 18 2b   JB    23h.0,A686h      ; skip if a report is already pending
A65B: 78 6c      MOV   R0,#6Ch          ; zero the 8-byte report buffer
A65D: 7f 08      MOV   R7,#08h
A65F: e4         CLR   A
A660: f6         MOV   @R0,A
A661: 08         INC   R0
A662: df fc      DJNZ  R7,A660h
A664: 78 7e      MOV   R0,#7Eh          ; zero the NKRO buffer
A666: 7f 10      MOV   R7,#10h
A668: e4         CLR   A
A669: f6         MOV   @R0,A
A66A: 08         INC   R0
A66B: df fc      DJNZ  R7,A669h
A66D: d2 18      SETB  23h.0            ; mark both reports pending ("all up")
A66F: d2 3e      SETB  27h.6
A671: 80 13      SJMP  A686h
A673: e5 4f      MOV   A,4Fh            ; held: about every 20 ms ...
A675: 20 e0 0e   JB    ACC.0,A686h
A678: e5 53      MOV   A,53h
A67A: c3         CLR   C
A67B: 94 02      SUBB  A,#02h
A67D: 50 07      JNC   A686h
A67F: 20 18 04   JB    23h.0,A686h
A682: d2 18      SETB  23h.0            ; ... re-send the CURRENT report unchanged
A684: d2 3e      SETB  27h.6
A686: 02 8d af   LJMP  8DAFh            ; original 8-byte sender
```

v8 is the same routine without the "held" branch (52 bytes): if any key is down it jumps straight to the sender.

## Recovery

Keep the stock hex (and v7/v8) on the PC. Flash any of them the same way as the patched image (see the research document, section 13).
Do not flash another keyboard's firmware or these images on a different model.
