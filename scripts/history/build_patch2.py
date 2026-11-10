#!/usr/bin/env python3
# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
"""v2 RAM-frame patch for the Rapoo V720 (SH68F89-class: XRAM only 0x0000-0x0AFF).
Layer-0 colour planes (3 x 0x84 bytes, page 0xAC00..0xAD8B) are held in three XRAM gaps
that the firmware never touches.  usage: build_patch2.py <stock.bin> <out.bin>"""
import sys, hashlib

CAVE = 0xA500
PLANE = 0x84
M0, M1 = 0x0140, 0x0400          # plane0 -> M0 ; plane1 -> M1 ; plane2 -> M1+0x84 (=0x0484)
M2 = M1 + PLANE


def lj(a): return bytes([0x02, a >> 8, a & 0xFF])
def lc(a): return bytes([0x12, a >> 8, a & 0xFF])


def build(stock):
    mem = bytearray(stock)
    changes = []

    def patch(addr, old, new, why):
        assert bytes(mem[addr:addr + len(old)]) == bytes(old), (hex(addr), mem[addr:addr + len(old)].hex(), bytes(old).hex())
        assert len(old) == len(new)
        mem[addr:addr + len(new)] = new
        changes.append((addr, bytes(old), bytes(new), why))

    cave = bytearray()

    def here(): return CAVE + len(cave)
    def emit(*b): cave.extend(b)

    def rel_to(target, next_pc):
        d = target - next_pc
        assert -128 <= d <= 127, d
        return d & 0xFF

    # ---- subroutine X: copy one plane  XRAM[R4:R5] -> XRAM[R2:R3], 0x84 bytes (src/dst advance)
    plane_x = here()
    emit(0x7F, PLANE)                          # MOV R7,#84h
    l = here()
    emit(0x8C, 0x83, 0x8D, 0x82, 0xE0, 0xA3)   # DPH=R4 ; DPL=R5 ; MOVX A,@DPTR ; INC DPTR
    emit(0xAC, 0x83, 0xAD, 0x82)               # R4=DPH ; R5=DPL
    emit(0x8A, 0x83, 0x8B, 0x82, 0xF0, 0xA3)   # DPH=R2 ; DPL=R3 ; MOVX @DPTR,A ; INC DPTR
    emit(0xAA, 0x83, 0xAB, 0x82)               # R2=DPH ; R3=DPL
    emit(0xDF, rel_to(l, here() + 2))          # DJNZ R7,l
    emit(0x22)

    # ---- subroutine C: same but source is CODE flash (MOVC)
    plane_c = here()
    emit(0x7F, PLANE)
    l = here()
    emit(0x8C, 0x83, 0x8D, 0x82, 0xE4, 0x93, 0xA3)   # DPH=R4 ; DPL=R5 ; CLR A ; MOVC A,@A+DPTR ; INC DPTR
    emit(0xAC, 0x83, 0xAD, 0x82)
    emit(0x8A, 0x83, 0x8B, 0x82, 0xF0, 0xA3)
    emit(0xAA, 0x83, 0xAB, 0x82)
    emit(0xDF, rel_to(l, here() + 2))
    emit(0x22)

    # ---- copy driver from staging buffer (hook) : 05D1 -> three planes
    drv_x = here()
    emit(0x7C, 0x05, 0x7D, 0xD1)               # R4:R5 = 05D1
    emit(0x7A, M0 >> 8, 0x7B, M0 & 0xFF)       # R2:R3 = M0
    emit(*lc(plane_x))
    emit(0x7A, M1 >> 8, 0x7B, M1 & 0xFF)       # R2:R3 = M1  (plane2 continues at M1+0x84)
    emit(*lc(plane_x))
    emit(*lc(plane_x))
    emit(0x22)

    # ---- (A) hook at 0x3E9E : internal frame-page save -> RAM instead of erase/program
    hook = here()
    emit(0x78, 0x25, 0xE2)
    fix1 = len(cave); emit(0xB4, 0xAC, 0x00)
    emit(0x78, 0x1D, 0xE2)
    fix2 = len(cave); emit(0xB4, 0xAC, 0x00)
    emit(*lc(drv_x))
    emit(*lj(0x3F14))
    orig = here()
    emit(0xA2, 0xAF, 0x92, 0x52)
    emit(*lj(0x3EA2))
    cave[fix1 + 2] = rel_to(orig, CAVE + fix1 + 3)
    cave[fix2 + 2] = rel_to(orig, CAVE + fix2 + 3)

    # ---- (A2) hook at 0x9DE0 : HOST page write, destination page 0xAC -> RAM
    hook2 = here()
    emit(0xE5, 0x49)                            # MOV A,49h  (dest page high byte parsed from the report header)
    fix4 = len(cave); emit(0xB4, 0xAC, 0x00)
    emit(*lc(drv_x))
    emit(0x22)
    orig2 = here()
    emit(0xA2, 0xAF, 0x92, 0x54)
    emit(*lj(0x9DE4))
    cave[fix4 + 2] = rel_to(orig2, CAVE + fix4 + 3)

    # ---- (B) boot copy at 0x5C16 : flash 0xAC00 planes -> RAM
    boot = here()
    emit(0x7C, 0xAC, 0x7D, 0x00)               # R4:R5 = AC00
    emit(0x7A, M0 >> 8, 0x7B, M0 & 0xFF)
    emit(*lc(plane_c))
    emit(0x7A, M1 >> 8, 0x7B, M1 & 0xFF)
    emit(*lc(plane_c))
    emit(*lc(plane_c))
    emit(0x53, 0x86, 0x3F)                      # original instruction at 5C16
    emit(*lj(0x5C19))

    # ---- (C) layer-0 third plane tail (shared tail 26AD stays flash for other layers)
    c3 = here()
    emit(0xF5, 0x82, 0xE4, 0x35, 0x83, 0xF5, 0x83)
    emit(0xE0, 0xFD)
    emit(*lj(0x26B7))

    assert here() <= CAVE + 0x200
    assert all(b == 0 for b in mem[CAVE:CAVE + len(cave)])
    old = bytes(mem[CAVE:CAVE + len(cave)])
    mem[CAVE:CAVE + len(cave)] = cave
    changes.append((CAVE, old, bytes(cave), "new code in unused flash"))

    # ---------------- patches of existing code
    patch(0x3E9E, mem[0x3E9E:0x3EA1], lj(hook), "internal save routine -> hook (page 0xAC to RAM)")
    patch(0x9DE0, mem[0x9DE0:0x9DE3], lj(hook2), "HOST page-write routine -> hook (page 0xAC to RAM, no erase/program)")
    patch(0x5C16, mem[0x5C16:0x5C19], lj(boot), "startup -> boot copy of the saved painting into RAM")
    patch(0x2543, mem[0x2543:0x2546], lj(c3), "layer0 3rd plane: RAM tail")
    for a, hi, lo in ((0x24FD, M0 >> 8, M0 & 0xFF), (0x251B, M1 >> 8, M1 & 0xFF), (0x253B, M2 >> 8, M2 & 0xFF)):
        patch(a, mem[a:a + 2], bytes([hi, lo]), "layer0 plane base address -> XRAM")
    for a in (0x250C, 0x252A):
        patch(a, bytes([0xE4, 0x93]), bytes([0xE0, 0x00]), "CLR A;MOVC A,@A+DPTR -> MOVX A,@DPTR;NOP")
    return bytes(mem), changes, dict(hook=hook, hook2=hook2, boot=boot, c3=c3, drv_x=drv_x, plane_x=plane_x, plane_c=plane_c)


if __name__ == "__main__":
    stock = open(sys.argv[1], "rb").read()
    out, changes, addrs = build(stock)
    open(sys.argv[2], "wb").write(out)
    n = 0
    for a, o, nw, why in changes:
        n += sum(1 for x, y in zip(o, nw) if x != y)
        print("%04X  %s -> %s   %s" % (a, o.hex(" ") if len(o) <= 12 else "(%d bytes)" % len(o),
                                        nw.hex(" ") if len(nw) <= 12 else "(%d bytes)" % len(nw), why))
    print("bytes changed:", n, " md5 out:", hashlib.md5(out).hexdigest())
    print({k: hex(v) for k, v in addrs.items()})
