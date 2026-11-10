#!/usr/bin/env python3
# usage: test_v7.py <stock_dump>   (builds v7 in memory and compares the new report against the stock LED renderer)
# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
import sys, random
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim51 import CPU
import fwtools, build_v7
stock = bytes(fwtools.load(sys.argv[1]))
patched = build_v7.build(stock)
rnd = random.Random(11); fails = 0; S0 = {}
def check(n, ok, extra=""):
    global fails
    print(("PASS " if ok else "FAIL ") + n, extra)
    if not ok: fails += 1
SENT = 0xFFF0
def stock_render(idx, col, b7, lock):
    img = bytearray(stock)
    for ch in range(3): img[0xAC00 + ch*0x84 + idx] = col[ch]      # col = (B,G,R)
    c = CPU(bytes(img)); c.sfr[0x81] = 0x30; c.iram[0xB7] = b7
    c.xram[0x25] = 0; c.xram[0x26] = 0; c.xram[0x27] = 0
    c.push(SENT & 0xFF); c.push(SENT >> 8); c.pc = 0x24CF; c.iram[0x07] = 0
    c.run({SENT}, limit=3000000)
    return c
def patched_run(idx, rgb, b7, lock_setup=None, pre=None):
    c = CPU(patched); c.sfr[0x81] = 0x30; c.iram[0xB7] = b7
    if pre: pre(c)
    c.xram[4] = 0x0B; c.xram[5] = 0x28
    c.xram[0x0B28:0x0B2E] = bytes([5, 0xE0, idx, rgb[0], rgb[1], rgb[2]])
    base = bytes(c.xram)
    c.pc = 0x5358; c.iram[0x46] = 7
    c.run({0x5480}, limit=100000)
    return c, base
try:
    VALID = [i for i in range(132)]
    nbad = ntot = 0; changed_outside = 0; skipped = 0
    for b7 in (1,2,4):
        for idx in range(132):
            col = (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))   # B,G,R
            s = stock_render(idx, col, b7, None); s0 = stock_render(idx, (0,0,0), b7, None)
            p, base = patched_run(idx, (col[2], col[1], col[0]), b7)
            # find where stock wrote nonzero (relative to a blank render)
            ntot += 1
            diff = [a for a in range(0x0B00) if p.xram[a] != base[a] and not (0x0130 <= a < 0x0138)]
            sdiff = [a for a in list(range(0x01D9, 0x0365)) + list(range(0x0386, 0x0512)) if s.xram[a] != s0.xram[a]]
            ok = set(sdiff) <= set(diff) and all(p.xram[a] == col[(a - 0x0386) % 3 if a >= 0x0386 else (a - 0x01D9) % 3] for a in diff)   # v7: raw colour, a superset of the addresses the stock renderer changes (stock skips values that scale to 0)
            if not ok:
                nbad += 1
                if nbad < 6: print("  idx", idx, "b7", b7, "col", col, "patched", [(hex(a), p.xram[a]) for a in diff], "stock", [(hex(a), s.xram[a]) for a in sdiff])
            if p.iram[0x46] != 0 or p.pc != 0x5480: check("ack state idx%d" % idx, False)
    check("every idx x 5 brightness writes raw colour to the a superset of the addresses the stock renderer changes (stock skips values that scale to 0) (%d cases)" % ntot, nbad == 0, "bad=%d" % nbad)
except Exception as e:
    import traceback; traceback.print_exc(); fails += 1
# passthrough: non-matching report takes original path
def run_other(rep):
    c = CPU(patched); c.sfr[0x81] = 0x30
    c.xram[4] = 0x0B; c.xram[5] = 0x28; c.xram[0x0B28:0x0B2E] = bytes(rep)
    o = CPU(stock); o.sfr[0x81] = 0x30
    o.xram[4] = 0x0B; o.xram[5] = 0x28; o.xram[0x0B28:0x0B2E] = bytes(rep)
    for x in (c, o): x.pc = 0x5358; x.iram[0x46] = 7
    try: c.run({0x5480}, limit=100000)
    except RuntimeError: pass
    try: o.run({0x5480}, limit=100000)
    except RuntimeError: pass
    return bytes(c.xram) == bytes(o.xram) and c.iram == o.iram
for rep in ([5,0x83,0,0,0,0],[5,0xE1,1,2,3,4],[6,0xE0,1,2,3,4],[5,0x75,0,0,0,0],[5,0xA5,1,1,1,1],[5,1,0,0,0,0]):
    check("passthrough %s == stock" % bytes(rep).hex(" "), run_other(rep))
# out-of-range idx writes nothing
c, base = patched_run(200, (9, 9, 9), 3)
check("idx 200 changes nothing", [a for a in range(0x0B00) if c.xram[a] != base[a] and not (0x130 <= a < 0x138)] == [])
print("FAILS", fails)
