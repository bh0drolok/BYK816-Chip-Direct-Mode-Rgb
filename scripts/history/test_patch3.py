#!/usr/bin/env python3
# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
import sys, random
S = sys.argv[1]; sys.path.insert(0, S + "/tools")
from sim51 import CPU
stock = open(S + "/dump/v720_full.bin", "rb").read()
patched = open(S + "/patch/v720_stream3.bin", "rb").read()
TAG = bytes([0x52, 0x54, 0x56, 0x32]); TAGOFF = 0x318; STG = 0x05D1
rnd = random.Random(7); fails = 0
def check(n, ok, extra=""):
    global fails
    print(("PASS " if ok else "FAIL ") + n, extra)
    if not ok: fails += 1
def with_flash(img, frame):
    b = bytearray(img); b[0xAC00:0xAC00+len(frame)] = frame; return bytes(b)
def rnd_frame(): return bytes(rnd.randrange(1, 256) for _ in range(0x400))
def tagged(frame):
    f = bytearray(frame); f[TAGOFF:TAGOFF+4] = TAG; return bytes(f)
def render(img, staging, layer, row, col):
    c = CPU(img); c.sfr[0x81] = 0x30
    if staging is not None: c.xram[STG:STG+0x400] = staging
    c.xram[0x25] = layer; c.xram[0x26] = row; c.xram[0x27] = col; c.pc = 0x24E0
    try: c.run({0x2864}, limit=20000)
    except RuntimeError as e: return ("ERR", str(e)[:30])
    return bytes(c.xram[0x20:0x30])

# T1: no tag in staging (and garbage staging) -> identical to stock for all layers/keys
bad = n = 0
for t in range(2):
    fr = rnd_frame(); o = with_flash(stock, fr); p = with_flash(patched, fr)
    junk = bytes(rnd.randrange(256) for _ in range(0x400)); junk = junk[:TAGOFF] + b"\0\0\0\0" + junk[TAGOFF+4:]
    for layer in range(7):
        for row in range(6):
            for col in range(22):
                n += 1
                if render(o, None, layer, row, col) != render(p, junk if t else None, layer, row, col): bad += 1
check("T1 no tag: renderer == stock, 7 layers x 132 keys x2 (%d cases)" % n, bad == 0, "bad=%d" % bad)
# T1b one tag byte wrong -> flash
fr = rnd_frame(); p = with_flash(patched, fr); o = with_flash(stock, fr)
for k in range(4):
    st = bytearray(tagged(rnd_frame())); st[TAGOFF+k] ^= 1
    ok = all(render(o, None, 0, r, c_) == render(p, bytes(st), 0, r, c_) for r in range(6) for c_ in range(22))
    check("T1b tag byte %d wrong -> reads flash" % k, ok)
# T2: tag present -> layer0 equals stock-with-those-planes-in-flash; layer 1+ still flash
bad = n = 0
for t in range(3):
    st = tagged(rnd_frame()); flash_other = rnd_frame()
    o = with_flash(stock, st)                       # stock rendering the same planes from flash
    p = with_flash(patched, flash_other)            # patched: flash holds something else, staging holds the frame
    for row in range(6):
        for col in range(22):
            n += 1
            if render(o, None, 0, row, col) != render(p, st, 0, row, col): bad += 1
check("T2 tag: layer0 renders staging planes == stock rendering them from flash (%d keys)" % n, bad == 0, "bad=%d" % bad)
st = tagged(bytes([0x77]) * 0x400); p = with_flash(patched, rnd_frame())
r0 = render(p, st, 0, 1, 3); r1 = render(p, st, 1, 1, 3); r6 = render(p, st, 6, 1, 3)
o1 = render(with_flash(stock, rnd_frame()), None, 1, 1, 3)
check("T2b layer0 follows staging", r0 != render(p, None, 0, 1, 3))
check("T2b layers 1 and 6 ignore staging", r1 == render(p, None, 1, 1, 3) and r6 == render(p, None, 6, 1, 3))
# T3: hook at 9DE0
def hook(page, typ, staging, sp=0x30):
    c = CPU(with_flash(patched, rnd_frame())); c.sfr[0x81] = sp; c.sfr[0xA8] = 0x80
    c.xram[STG:STG+0x400] = staging; c.iram[0x49] = page; c.iram[0x4A] = 0; c.iram[0x48] = typ
    c.sfr[0xE0] = 0x5A; c.sfr[0x83] = 0x12; c.sfr[0x82] = 0x34
    c.push(0x34); c.push(0x12); c.pc = 0x9DE0
    seen = {}
    try: c.run({0x1234, 0x9DE4})
    except RuntimeError as e: seen['err'] = str(e)[:40]
    return c
fr = tagged(rnd_frame())
c = hook(0xAC, 9, fr)
check("T3 tagged AC/type9: returns to caller, skips flash code", c.pc == 0x1234 and c.sfr[0x81] == 0x30 and not any(k in c.sfr for k in (0xF2,0xF3,0xF4,0xF5,0xF6,0xF7)))
check("T3 tagged: A and DPTR preserved", c.sfr[0xE0] == 0x5A and (c.sfr[0x83], c.sfr[0x82]) == (0x12, 0x34), (hex(c.sfr[0xE0]), hex(c.sfr[0x83]), hex(c.sfr[0x82])))
check("T3 tagged: staging untouched", bytes(c.xram[STG:STG+0x400]) == fr)
for name, page, typ, st in (("untagged AC type9", 0xAC, 9, rnd_frame()), ("tagged but page C8", 0xC8, 9, fr), ("tagged AC but type 5", 0xAC, 5, fr)):
    c = hook(page, typ, st)
    check("T3 %s: original path reached (9DE4), IE saved, A/DPTR preserved, stack balanced" % name,
          c.pc == 0x9DE4 and c.bget(0x54) == 1 and c.sfr[0xE0] == 0x5A and (c.sfr[0x83], c.sfr[0x82]) == (0x12, 0x34) and c.sfr[0x81] == 0x32,
          "pc=%04X sp=%02X" % (c.pc, c.sfr[0x81]))
# T4: all other flash bytes identical to stock
diff = [i for i in range(len(stock)) if stock[i] != patched[i]]
allowed = set(range(0xA500, 0xA586)) | {0x9DE0,0x9DE1,0x9DE2,0x250C,0x250D,0x250E,0x252A,0x252B,0x252C,0x2543,0x2544,0x2545}
check("T4 only intended bytes differ from stock (%d bytes)" % len(diff), set(diff) <= allowed and max(diff) < 0xF000)
print("ALL PASS" if not fails else "FAILURES %d" % fails); sys.exit(1 if fails else 0)
