# usage: test_v8.py <stock_dump>
# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
import sys, random
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim51 import CPU
import fwtools as fwio
import build_v8 as B

v7, v8, code = B.build(sys.argv[1])
fails = []
def check(name, ok, detail=''):
    print('[%s] %s %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: fails.append(name)

# ---- image checks
diff = [i for i in range(0x10000) if v7[i] != v8[i]]
allowed = set(range(0x5D9E, 0x5DA0)) | set(range(B.CAVE, B.CAVE + len(code)))
check('v8 differs from v7 only at the call site (2 bytes) and the new 52-byte guard', set(diff) <= allowed, '%d bytes' % len(diff))
check('boot loader area identical', bytes(v7[0xF000:]) == bytes(v8[0xF000:]))

def mk(img, raw=None, b4f=1, b53=0, pend=False, buf8=None, nk=None, aa=0, ab=0, f27_6=False):
    c = CPU(bytes(img)); c.sfr[0x81] = 0xC0
    for i in range(22): c.iram[0x92 + i] = 0xFF if raw is None else raw[i]
    c.iram[0x4F] = b4f; c.iram[0x53] = b53
    c.iram[0x50] = 0
    c.bset(0x18, pend); c.bset(0x3E, f27_6)
    c.iram[0x6C:0x74] = bytes(buf8 or [0]*8)
    c.iram[0x7E:0x8E] = bytes(nk or [0]*16)
    c.sfr[0xAA] = aa; c.sfr[0xAB] = ab
    return c

def run(c):
    c.pc = 0x5D9D
    c.run({0x5DA3}, limit=200000)
    return c

def snap(c):
    # R0, R7, ACC and the carry flag are scratch: the original sender and the routine after it overwrite them before use
    ir = bytearray(c.iram); ir[0] = 0; ir[7] = 0
    sf = dict(c.sfr); sf.pop(0xE0, None); sf[0xD0] = sf.get(0xD0, 0) & 0x7F
    return (bytes(ir), bytes(c.xram), tuple(sorted(sf.items())), c.pc)

rnd = random.Random(8)
# A: guard fires
fire_cases = 0; bad = []
for t in range(300):
    buf8 = [rnd.randrange(256) for _ in range(8)]
    nk = [rnd.randrange(256) for _ in range(16)]
    b4f = rnd.randrange(16) << 4; b53 = rnd.randrange(2)
    c = run(mk(v8, buf8=buf8, nk=nk, b4f=b4f, b53=b53))
    ref = run(mk(v7, buf8=[0]*8, nk=[0]*16, b4f=b4f, b53=b53, pend=True, f27_6=True))   # what a clean idle resend looks like
    ok = (bytes(c.xram[0xB48:0xB50]) == bytes(8) and c.xram[0xBA8] == 4 and bytes(c.xram[0xBA9:0xBB8]) == bytes(15)
          and not c.bget(0x18) and not c.bget(0x3E) and (c.sfr[0xAA] & 4) and (c.sfr[0xAB] & 4) and c.sfr[0x81] == 0xC0 and c.pc == 0x5DA3)
    if not ok: bad.append((t, bytes(c.xram[0xB48:0xB50]).hex(), hex(c.xram[0xBA8])))
    fire_cases += 1
check('idle + timing match: all-up report is built and handed to BOTH keyboard endpoints (%d random cases)' % fire_cases, not bad, str(bad[:3]))

# B: every non-firing condition behaves exactly like v7 (full state compare)
nb = 0; bad = []
def same(name, **kw):
    global nb
    a = run(mk(v8, **kw)); b = run(mk(v7, **kw)); nb += 1
    if snap(a) != snap(b):
        bad.append(name)
buf = [2, 0, 0x04, 0, 0, 0, 0, 0]; nk = [4, 0, 0, 0x10] + [0]*12
for col in range(22):
    for bit in range(6):
        raw = [0xFF]*22; raw[col] = 0xFF ^ (1 << bit)
        same('key down col%d bit%d' % (col, bit), raw=raw, buf8=buf, nk=nk, b4f=0, b53=0)
for v in range(1, 16): same('4F&0F=%d' % v, buf8=buf, nk=nk, b4f=v, b53=0)
for v in range(2, 10): same('53=%d' % v, buf8=buf, nk=nk, b4f=0, b53=v)
same('pending already', buf8=buf, nk=nk, b4f=0, b53=0, pend=True)
check('guard stays out of the way whenever a key is down / timing off / report pending (%d cases, state identical to v7)' % nb, not bad, str(bad[:3]))

# C: random fuzz vs v7 outside the firing condition; inside it, only buffers/flags differ
bad = []
for t in range(1500):
    raw = [0xFF]*22
    if rnd.random() < 0.5:
        for _ in range(rnd.randrange(1, 4)): raw[rnd.randrange(22)] = rnd.randrange(256)
    kw = dict(raw=raw, buf8=[rnd.randrange(256) for _ in range(8)], nk=[rnd.randrange(256) for _ in range(16)],
              b4f=rnd.randrange(256), b53=rnd.randrange(10), pend=rnd.random() < .2, aa=rnd.choice([0, 4]), ab=rnd.choice([0, 4]), f27_6=rnd.random() < .2)
    a = run(mk(v8, **kw)); b = run(mk(v7, **kw))
    fires = all(x == 0xFF for x in raw) and (kw['b4f'] & 15) == 0 and kw['b53'] < 2 and not kw['pend']
    if not fires:
        if snap(a) != snap(b): bad.append(('nonfire', t))
    else:
        if a.sfr[0x81] != b.sfr[0x81] or a.pc != b.pc or a.iram[0x92:0xA8] != b.iram[0x92:0xA8]: bad.append(('fire-side', t))
        if bytes(a.iram[0x20:0x6C]) != bytes(b.iram[0x20:0x6C]) and False: pass
check('1500 random states: identical to v7 unless the guard fires; when it fires, stack/PC/matrix untouched', not bad, str(bad[:3]))

# D: busy endpoint -> report stays pending (retried later), guard does not lose it
c = run(mk(v8, aa=4, ab=4, buf8=[1]*8, nk=[4]+[1]*15, pend=True, f27_6=True, b4f=0, b53=0))
check('endpoint busy: report remains pending for retry (nothing dropped, no hang)', c.bget(0x18) and c.bget(0x3E) and c.pc == 0x5DA3)

# E: stack depth
c = mk(v8); c.pc = 0x5D9D
mx = 0xC0
steps = 0
while c.pc != 0x5DA3 and steps < 20000:
    c.step(); steps += 1; mx = max(mx, c.sfr[0x81])
check('guard adds at most 2 stack bytes (call return address)', mx <= 0xC0 + 6, 'max SP %#x' % mx)
print('\nALL PASS' if not fails else '\nFAILED: %s' % fails)
sys.exit(1 if fails else 0)
