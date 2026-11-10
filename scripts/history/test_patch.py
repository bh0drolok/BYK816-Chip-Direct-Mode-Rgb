#!/usr/bin/env python3
# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
import sys, random
sys.path.insert(0, sys.argv[1] + "/tools")
from sim51 import CPU

S = sys.argv[1]
stock = bytearray(open(S + "/dump/v720_full.bin", "rb").read())
patched = bytearray(open(S + "/patch/v720_ramframe.bin", "rb").read())
SIZE = 0x318
MIR = 0x0C00
rnd = random.Random(1234)


def with_frame(img, frame):
    b = bytearray(img)
    b[0xAC00:0xAC00 + len(frame)] = frame
    return bytes(b)


fails = 0


def check(name, ok, extra=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name, extra)
    if not ok:
        fails += 1


# ---------- T1 boot copy
frame = bytes(rnd.randrange(256) for _ in range(SIZE))
cpu = CPU(with_frame(patched, frame))
cpu.sfr[0x81] = 0x30
cpu.sfr[0x86] = 0xFF
cpu.pc = 0x5C16
cpu.run({0x5C19})
check("T1 boot copy flash->RAM", bytes(cpu.xram[MIR:MIR + SIZE]) == frame)
check("T1 original instruction ANL 86,#3F executed", cpu.sfr[0x86] == 0x3F)
check("T1 nothing outside mirror touched", all(v == 0 for v in cpu.xram[:MIR]) and all(v == 0 for v in cpu.xram[MIR + SIZE:]))

# ---------- T2 renderer equivalence
def render(img, mirror, layer, row, col):
    c = CPU(img)
    c.sfr[0x81] = 0x30
    if mirror is not None:
        c.xram[MIR:MIR + SIZE] = mirror
    c.xram[0x25] = layer
    c.xram[0x26] = row
    c.xram[0x27] = col
    c.pc = 0x24E0
    try:
        c.run({0x2864}, limit=20000)
    except RuntimeError as e:
        return ("ERR", str(e)[:40])
    return bytes(c.xram[0x2A:0x30]) + bytes(c.xram[0x20:0x25])

mism = 0
checked = 0
for trial in range(2):
    frame = bytes(rnd.randrange(1, 256) for _ in range(SIZE))
    o = with_frame(stock, frame)
    p = with_frame(patched, frame)
    for layer in range(0, 7):
        for row in range(6):
            for col in range(22):
                a = render(o, None, layer, row, col)
                b = render(p, frame, layer, row, col)
                checked += 1
                if a != b:
                    mism += 1
                    if mism < 5:
                        print("  mismatch layer", layer, row, col, a, b)
check("T2 renderer output identical, all layers 0-6 x 132 keys x2 frames (%d cases)" % checked, mism == 0, "mismatches=%d" % mism)

# check renderer really reads RAM for layer 0/1 (change flash after the fact => no effect; change mirror => effect)
frame = bytes(rnd.randrange(1, 256) for _ in range(SIZE))
p = with_frame(patched, frame)
junk = bytes(0x55 for _ in range(SIZE))
r_ram = render(p, junk, 0, 1, 3)
r_ram1 = render(p, junk, 1, 1, 3)
check("T2b layer0/1 colors come from RAM (value 0x55 expected)", r_ram[:6] != render(p, frame, 0, 1, 3)[:6] and 0x55 in r_ram[:6] and 0x55 in r_ram1[:6], str((bytes(r_ram[:6]).hex(), bytes(r_ram1[:6]).hex())))

# ---------- T3 hook + merge helper
def setup_save(img, page, offset, buf, mirror=None):
    c = CPU(img)
    c.sfr[0x81] = 0x30
    c.xram[0x1D] = page; c.xram[0x1E] = 0
    c.xram[0x1F] = offset >> 8; c.xram[0x20] = offset & 0xFF
    c.xram[0x25] = page
    c.xram[0x23] = 0; c.xram[0x24] = 0
    c.xram[0x05D1:0x05D1 + 0x400] = buf
    if mirror is not None:
        c.xram[MIR:MIR + SIZE] = mirror
    return c

for offset in (0x018C, 0x0000):
    frame = bytes(rnd.randrange(256) for _ in range(SIZE))
    buf = bytes(rnd.randrange(256) for _ in range(0x400))
    # original: merge only (stop before erase/program)
    co = setup_save(with_frame(stock, frame), 0xAC, offset, buf)
    co.pc = 0x3E57; co.run({0x3E9E})
    merged_orig = bytes(co.xram[0x05D1:0x05D1 + 0x400])
    # patched, mirror == flash
    cp = setup_save(with_frame(patched, frame), 0xAC, offset, buf, mirror=frame)
    cp.pc = 0x3E57; cp.run({0x3F14})
    check("T3 offset %04X: merged buffer same as original (mirror==flash)" % offset, bytes(cp.xram[0x05D1:0x05D1 + 0x400]) == merged_orig)
    check("T3 offset %04X: mirror == merged page image, hook ended at 3F14" % offset, bytes(cp.xram[MIR:MIR + SIZE]) == merged_orig[:SIZE])
    # patched, stale flash vs fresher mirror: preserved part must come from the mirror
    newer = bytes(rnd.randrange(256) for _ in range(SIZE))
    cp = setup_save(with_frame(patched, frame), 0xAC, offset, buf, mirror=newer)
    cp.pc = 0x3E57; cp.run({0x3F14})
    out = bytes(cp.xram[MIR:MIR + SIZE])
    keep = range(offset, offset + 0x18C)
    ok = all(out[i] == newer[i] for i in keep) and all(out[i] == buf[i] for i in range(SIZE) if i not in keep)
    check("T3 offset %04X: preserved half taken from RAM mirror, new half from host buffer" % offset, ok)

# non-frame page keeps the ORIGINAL path (reaches 3EA2 with the same merged buffer, flash MOVC)
for page in (0xB0, 0xB8):
    frame = bytes(rnd.randrange(256) for _ in range(0x400))
    buf = bytes(rnd.randrange(256) for _ in range(0x400))
    img_o = bytearray(stock); img_o[page << 8:(page << 8) + 0x400] = frame
    img_p = bytearray(patched); img_p[page << 8:(page << 8) + 0x400] = frame
    co = setup_save(bytes(img_o), page, 0x018C, buf); co.pc = 0x3E57; co.run({0x3E9E})
    cp = setup_save(bytes(img_p), page, 0x018C, buf, mirror=bytes(SIZE)); cp.sfr[0xA8] = 0x80
    cp.pc = 0x3E57; cp.run({0x3EA2})
    check("T3 page %02X00 untouched path: same merge, falls through to original code at 3EA2" % page,
          bytes(cp.xram[0x05D1:0x05D1 + 0x400]) == bytes(co.xram[0x05D1:0x05D1 + 0x400]) and cp.bget(0x52) == 1 and bytes(cp.xram[MIR:MIR + SIZE]) == bytes(SIZE))

print("ALL PASS" if fails == 0 else "FAILURES: %d" % fails)
sys.exit(1 if fails else 0)
