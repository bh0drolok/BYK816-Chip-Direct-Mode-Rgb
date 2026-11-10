#!/usr/bin/env python3
# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
"""Build the RAM-frame patch for the Rapoo V720 stock firmware.
usage: build_patch.py <stock.bin> <out.bin>   (prints the full change list)"""
import sys, hashlib

MIRROR = 0x0C00       # XRAM mirror base of the 0xAC00 frame page (0x318 bytes)
CAVE = 0xA500         # unused (all-zero) flash
SIZE = 0x0318


def lj(a):
    return bytes([0x02, a >> 8, a & 0xFF])


def lc(a):
    return bytes([0x12, a >> 8, a & 0xFF])


def build(stock):
    mem = bytearray(stock)
    changes = []   # (addr, old, new, why)

    def patch(addr, old, new, why):
        assert bytes(mem[addr:addr + len(old)]) == bytes(old), (hex(addr), mem[addr:addr + len(old)].hex(), bytes(old).hex())
        assert len(old) == len(new)
        mem[addr:addr + len(new)] = new
        changes.append((addr, bytes(old), bytes(new), why))

    # ---------------- cave code (assembled by hand, labels resolved here)
    cave = bytearray()
    labels = {}

    def here():
        return CAVE + len(cave)

    def emit(*b):
        cave.extend(b)

    def rel_to(label_addr, next_pc):
        d = label_addr - next_pc
        assert -128 <= d <= 127, d
        return d & 0xFF

    # ---- shared subroutine: copy 0x318 bytes  XRAM 0x05D1 -> mirror
    copy = here()
    emit(0x7E, 0x00, 0x7F, 0x00)                # MOV R6,#0 ; MOV R7,#0
    cp = here()
    emit(0x74, 0xD1, 0x2F, 0xF5, 0x82)          # MOV A,#D1h ; ADD A,R7 ; MOV DPL,A
    emit(0x74, 0x05, 0x3E, 0xF5, 0x83)          # MOV A,#05h ; ADDC A,R6 ; MOV DPH,A
    emit(0xE0, 0xFD)                            # MOVX A,@DPTR ; MOV R5,A
    emit(0x8F, 0x82)                            # MOV DPL,R7
    emit(0x74, MIRROR >> 8, 0x2E, 0xF5, 0x83)   # MOV A,#hi ; ADD A,R6 ; MOV DPH,A
    emit(0xED, 0xF0)                            # MOV A,R5 ; MOVX @DPTR,A
    emit(0x0F, 0xEF, 0x70, 0x01, 0x0E)          # INC R7 ; MOV A,R7 ; JNZ +1 ; INC R6
    emit(0x64, SIZE & 0xFF)                     # XRL A,#lo
    emit(0x70, rel_to(cp, here() + 2))          # JNZ cp
    emit(0xEE, 0x64, SIZE >> 8)                 # MOV A,R6 ; XRL A,#hi
    emit(0x70, rel_to(cp, here() + 2))          # JNZ cp
    emit(0x22)                                  # RET

    # ---- (A) hook at 0x3E9E : internal frame-page save -> RAM instead of erase/program
    hook = here()
    emit(0x78, 0x25, 0xE2)                      # MOV R0,#25h ; MOVX A,@R0
    fix1 = len(cave); emit(0xB4, 0xAC, 0x00)    # CJNE A,#0ACh,orig
    emit(0x78, 0x1D, 0xE2)                      # MOV R0,#1Dh ; MOVX A,@R0
    fix2 = len(cave); emit(0xB4, 0xAC, 0x00)    # CJNE A,#0ACh,orig
    emit(*lc(copy))
    emit(*lj(0x3F14))                           # done: continue after the (skipped) flash write
    orig = here()
    emit(0xA2, 0xAF, 0x92, 0x52)                # original: MOV C,IE.7 ; MOV 2Ah.2,C
    emit(*lj(0x3EA2))
    cave[fix1 + 2] = rel_to(orig, CAVE + fix1 + 3)
    cave[fix2 + 2] = rel_to(orig, CAVE + fix2 + 3)

    # ---- (A2) hook at 0x9DE0 : HOST page write (report 06 <type> <addrhi> <addrlo>), page 0xAC -> RAM
    hook2 = here()
    emit(0xE5, 0x49)                            # MOV A,49h  (destination page, high byte)
    fix4 = len(cave); emit(0xB4, 0xAC, 0x00)    # CJNE A,#0ACh,orig2
    emit(*lc(copy))
    emit(0x22)                                  # RET to the report handler (flash write skipped)
    orig2 = here()
    emit(0xA2, 0xAF, 0x92, 0x54)                # original: MOV C,IE.7 ; MOV 2Ah.4,C
    emit(*lj(0x9DE4))
    cave[fix4 + 2] = rel_to(orig2, CAVE + fix4 + 3)

    # ---- (B) boot copy at 0x5C16 : flash frame page -> RAM mirror
    boot = here()
    emit(0x7E, 0x00, 0x7F, 0x00)
    bl = here()
    emit(0x8F, 0x82)                            # MOV DPL,R7
    emit(0x74, 0xAC, 0x2E, 0xF5, 0x83)          # MOV A,#0ACh ; ADD A,R6 ; MOV DPH,A
    emit(0xE4, 0x93, 0xFD)                      # CLR A ; MOVC A,@A+DPTR ; MOV R5,A
    emit(0x8F, 0x82)
    emit(0x74, MIRROR >> 8, 0x2E, 0xF5, 0x83)
    emit(0xED, 0xF0)
    emit(0x0F, 0xEF, 0x70, 0x01, 0x0E)
    emit(0x64, SIZE & 0xFF)
    emit(0x70, rel_to(bl, here() + 2))
    emit(0xEE, 0x64, SIZE >> 8)
    emit(0x70, rel_to(bl, here() + 2))
    emit(0x53, 0x86, 0x3F)                      # original instruction at 5C16
    emit(*lj(0x5C19))

    # ---- (C) layer-0 third plane tail (shared tail 26AD stays flash for other layers)
    c3 = here()
    emit(0xF5, 0x82, 0xE4, 0x35, 0x83, 0xF5, 0x83)   # MOV DPL,A ; CLR A ; ADDC A,DPH ; MOV DPH,A
    emit(0xE0, 0xFD)                                  # MOVX A,@DPTR ; MOV R5,A
    emit(*lj(0x26B7))

    # ---- (D) layer-1 third plane tail (copy of 2714..2726 reading RAM)
    c4 = here()
    emit(*lc(0x562B))
    emit(0xE5, 0x82, 0x2F, 0xF5, 0x82, 0xE4, 0x35, 0x83, 0xF5, 0x83)
    emit(0xE0, 0xFF, 0x78, 0x2A)                      # MOVX A,@DPTR ; MOV R7,A ; MOV R0,#2Ah
    emit(*lj(0x27DA))

    # ---- (E) merge-read helper: read the *old* page content from RAM when page == 0xAC
    mh = here()
    emit(0x79, 0x25, 0xE3)                      # MOV R1,#25h ; MOVX A,@R1
    fix3 = len(cave); emit(0xB4, 0xAC, 0x00)    # CJNE A,#0ACh,flash
    emit(0xE5, 0x83, 0xC3, 0x94, (0xAC - (MIRROR >> 8)) & 0xFF)
    # ^ MOV A,DPH ; CLR C ; SUBB A,#(0xAC - mirror_hi)
    emit(0xF5, 0x83, 0xE0, 0xFD, 0x22)          # MOV DPH,A ; MOVX A,@DPTR ; MOV R5,A ; RET
    flash = here()
    emit(0xE4, 0x93, 0xFD, 0x22)                # CLR A ; MOVC A,@A+DPTR ; MOV R5,A ; RET
    cave[fix3 + 2] = rel_to(flash, CAVE + fix3 + 3)

    assert here() <= CAVE + 0x200, "cave too big"
    assert all(b == 0 for b in mem[CAVE:CAVE + len(cave)]), "cave area not empty"
    old = bytes(mem[CAVE:CAVE + len(cave)])
    mem[CAVE:CAVE + len(cave)] = cave
    changes.append((CAVE, old, bytes(cave), "new code in unused flash (hook, boot copy, renderer tails, merge helper)"))

    # ---------------- patches of existing code
    patch(0x3E9E, mem[0x3E9E:0x3EA1], lj(hook), "internal save routine: jump to hook (skips erase/program/verify for frame page)")
    patch(0x9DE0, mem[0x9DE0:0x9DE3], lj(hook2), "HOST page-write routine: jump to hook (page 0xAC -> RAM, no erase/program)")
    patch(0x3E76, mem[0x3E76:0x3E79], lc(mh), "merge loop: read old page bytes via helper (RAM when page 0xAC)")
    patch(0x5C16, mem[0x5C16:0x5C19], lj(boot), "startup: jump to boot copy (flash frame -> RAM)")
    patch(0x2543, mem[0x2543:0x2546], lj(c3), "layer0 plane3: use RAM tail")
    patch(0x2599, mem[0x2599:0x259C], lj(c4), "layer1 plane3: use RAM tail")
    mh_ = MIRROR >> 8
    for a, hi_new in ((0x24FD, mh_ + 0x00), (0x251B, mh_ + 0x00), (0x253B, mh_ + 0x01),
                      (0x2556, mh_ + 0x01), (0x2574, mh_ + 0x02), (0x2597, mh_ + 0x02)):
        patch(a, bytes([mem[a]]), bytes([hi_new]), "renderer DPTR base high byte -> RAM mirror")
    for a in (0x250C, 0x252A, 0x2565, 0x2583):
        patch(a, bytes([0xE4, 0x93]), bytes([0xE0, 0x00]), "renderer: CLR A;MOVC -> MOVX A,@DPTR;NOP")
    return bytes(mem), changes, dict(hook=hook, hook2=hook2, copy=copy, boot=boot, c3=c3, c4=c4, mh=mh)


if __name__ == "__main__":
    stock = open(sys.argv[1], "rb").read()
    out, changes, addrs = build(stock)
    open(sys.argv[2], "wb").write(out)
    n = 0
    for a, o, nw, why in changes:
        n += sum(1 for x, y in zip(o, nw) if x != y)
        print("%04X  %s -> %s   %s" % (a, o.hex(" ") if len(o) <= 12 else "(%d bytes of 00)" % len(o),
                                        nw.hex(" ") if len(nw) <= 12 else "(%d bytes)" % len(nw), why))
    print("bytes changed:", n, " md5 out:", hashlib.md5(out).hexdigest())
    print({k: hex(v) for k, v in addrs.items()})
