#!/usr/bin/env python3
# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
import sys, random
S = sys.argv[1]
sys.path.insert(0, S + "/tools")
from sim51 import CPU
stock = open(S + "/dump/v720_full.bin", "rb").read()
patched = open(S + "/patch/v720_ramframe2.bin", "rb").read()
P = 0x84
M0, M1, M2 = 0x0140, 0x0400, 0x0484
rnd = random.Random(99)
fails = 0
def check(n, ok, extra=""):
    global fails
    print(("PASS " if ok else "FAIL ") + n, extra)
    if not ok: fails += 1
def with_frame(img, frame):
    b = bytearray(img); b[0xAC00:0xAC00 + len(frame)] = frame; return bytes(b)
def planes(c): return bytes(c.xram[M0:M0+P]) + bytes(c.xram[M1:M1+P]) + bytes(c.xram[M2:M2+P])
mirror_ranges = list(range(M0, M0+P)) + list(range(M1, M1+2*P))

# T1 boot copy
frame = bytes(rnd.randrange(256) for _ in range(0x400))
c = CPU(with_frame(patched, frame)); c.sfr[0x81] = 0x30; c.sfr[0x86] = 0xFF; c.pc = 0x5C16
c.run({0x5C19})
check("T1 boot: planes copied from flash AC00/AC84/AD08", planes(c) == frame[:3*P])
touched = [i for i in range(0x10000) if c.xram[i] and i not in set(mirror_ranges)]
check("T1 boot: nothing else in XRAM touched", not touched)
check("T1 boot: original ANL 86,#3F executed", c.sfr[0x86] == 0x3F)

# T2 renderer: stock(flash) vs patched(mirror loaded by the real boot code)
def boot_mirror(img):
    cc = CPU(img); cc.sfr[0x81] = 0x30; cc.pc = 0x5C16; cc.run({0x5C19}); return cc.xram
def render(img, xram_init, layer, row, col):
    c = CPU(img, bytearray(xram_init) if xram_init else None); c.sfr[0x81] = 0x30
    c.xram[0x25] = layer; c.xram[0x26] = row; c.xram[0x27] = col; c.pc = 0x24E0
    try: c.run({0x2864}, limit=20000)
    except RuntimeError as e: return ("ERR", str(e)[:30])
    return bytes(c.xram[0x20:0x30])
bad = n = 0
for trial in range(3):
    frame = bytes(rnd.randrange(1, 256) for _ in range(0x400))
    o = with_frame(stock, frame); p = with_frame(patched, frame)
    xr = boot_mirror(p)
    for layer in range(0, 7):
        for row in range(6):
            for col in range(22):
                n += 1
                a = render(o, None, layer, row, col); b = render(p, xr, layer, row, col)
                if a != b:
                    bad += 1
                    if bad < 4: print("  mismatch", layer, row, col, a, b)
check("T2 renderer identical to stock: 7 layers x 132 keys x 3 frames (%d cases)" % n, bad == 0, "bad=%d" % bad)
# proof layer 0 is read from RAM, layer 1 from flash
p = with_frame(patched, frame); xr = boot_mirror(p)
xr2 = bytearray(xr); xr2[M0:M0+P] = bytes([0x77]) * P; xr2[M1:M1+2*P] = bytes([0x77]) * (2*P)
r0 = render(p, xr2, 0, 1, 3); r1 = render(p, xr2, 1, 1, 3)
check("T2b layer0 follows RAM (0x77s), layer1 still follows flash", bytes(r0[10:16]).count(0x77) >= 3 and 0x77 not in bytes(r1[10:16]), (bytes(r0[10:16]).hex(), bytes(r1[10:16]).hex()))

# T3 HOST hook at 9DE0
frame = bytes(rnd.randrange(256) for _ in range(0x400))
buf = bytes(rnd.randrange(256) for _ in range(0x400))
c = CPU(with_frame(patched, frame)); c.sfr[0x81] = 0x30
c.xram[0x05D1:0x05D1+0x400] = buf; c.iram[0x49] = 0xAC; c.iram[0x4A] = 0x00
c.push(0x34); c.push(0x12); c.pc = 0x9DE0; c.run({0x1234})
check("T3 host page AC00: planes == first 3 planes of host buffer, returns to caller", planes(c) == buf[:3*P])
check("T3 host page AC00: flash controller never touched (SFR F2-F7)", not any(k in c.sfr for k in (0xF2,0xF3,0xF4,0xF5,0xF6,0xF7)))
check("T3 host page AC00: stack balanced", c.sfr[0x81] == 0x30)
c = CPU(with_frame(patched, frame)); c.sfr[0x81] = 0x30; c.sfr[0xA8] = 0x80
c.iram[0x49] = 0xC8; c.pc = 0x9DE0; c.run({0x9DE4})
check("T3 host other page (C800): original path reached at 9DE4, IE saved in 2Ah.4, mirror untouched", c.bget(0x54) == 1 and planes(c) == bytes(3*P))
# T3b internal hook
for offset in (0x018C, 0x0000):
    buf = bytes(rnd.randrange(256) for _ in range(0x400))
    c = CPU(with_frame(patched, frame)); c.sfr[0x81] = 0x30
    c.xram[0x1D] = 0xAC; c.xram[0x1E] = 0; c.xram[0x1F] = offset >> 8; c.xram[0x20] = offset & 0xFF; c.xram[0x25] = 0xAC
    c.xram[0x05D1:0x05D1+0x400] = buf; c.pc = 0x3E57; c.run({0x3F14})
    merged = bytes(c.xram[0x05D1:0x05D1+0x400])
    check("T3b internal save, offset %04X: mirror planes == merged page image" % offset, planes(c) == merged[:3*P])
print("ALL PASS" if not fails else "FAILURES %d" % fails)
sys.exit(1 if fails else 0)
