# usage: test_v9.py <stock_dump>
# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
import sys, random
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim51 import CPU
import build_v9 as B
v7, v9, code = B.build(sys.argv[1])
fails = []
def check(n, ok, d=''):
    print('[%s] %s %s' % ('PASS' if ok else 'FAIL', n, d)); 
    if not ok: fails.append(n)
diff = [i for i in range(0x10000) if v7[i] != v9[i]]
allowed = set(range(0x5D9E, 0x5DA0)) | set(range(B.CAVE, B.CAVE + len(code)))
check('only the call site (2 bytes) and the %d-byte guard differ from v7; boot area identical' % len(code), set(diff) <= allowed and bytes(v7[0xF000:]) == bytes(v9[0xF000:]), '%d bytes' % len(diff))

def mk(img, raw=None, b4f=1, b53=0, pend=False, buf8=None, nk=None, aa=0, ab=0, f27_6=False):
    c = CPU(bytes(img)); c.sfr[0x81] = 0xC0
    for i in range(22): c.iram[0x92 + i] = 0xFF if raw is None else raw[i]
    c.iram[0x4F] = b4f; c.iram[0x53] = b53; c.iram[0x50] = 0
    c.bset(0x18, pend); c.bset(0x3E, f27_6)
    c.iram[0x6C:0x74] = bytes(buf8 or [0]*8); c.iram[0x7E:0x8E] = bytes(nk or [0]*16)
    c.sfr[0xAA] = aa; c.sfr[0xAB] = ab
    return c
def run(c):
    c.pc = 0x5D9D; c.run({0x5DA3}, limit=200000); return c
def snap(c):
    ir = bytearray(c.iram); ir[0] = 0; ir[7] = 0
    sf = dict(c.sfr); sf.pop(0xE0, None); sf[0xD0] = sf.get(0xD0, 0) & 0x7F
    return (bytes(ir), bytes(c.xram), tuple(sorted(sf.items())), c.pc)

rnd = random.Random(9)
bad = []; n = {'idle_fire': 0, 'held_fire': 0, 'quiet': 0}
for t in range(4000):
    raw = [0xFF]*22
    if rnd.random() < 0.55:
        for _ in range(rnd.randrange(1, 4)): raw[rnd.randrange(22)] = rnd.choice([0xFE, 0xFD, 0xFB, 0xF7, 0xEF, 0xDF, rnd.randrange(256)])
    idle = all(x == 0xFF for x in raw)
    buf8 = [rnd.randrange(256) for _ in range(8)]; nk = [rnd.randrange(256) for _ in range(16)]
    b4f = rnd.randrange(256); b53 = rnd.randrange(10); pend = rnd.random() < .2; f276 = rnd.random() < .3
    aa = rnd.choice([0, 4]); ab = rnd.choice([0, 4])
    kw = dict(raw=raw, b4f=b4f, b53=b53, aa=aa, ab=ab)
    a = run(mk(v9, buf8=buf8, nk=nk, pend=pend, f27_6=f276, **kw))
    # oracle: the ORIGINAL v7 firmware started from the state the guard is specified to produce
    if idle and (b4f & 15) == 0 and b53 < 2 and not pend:
        ref = run(mk(v7, buf8=[0]*8, nk=[0]*16, pend=True, f27_6=True, **kw)); kind = 'idle_fire'
    elif (not idle) and (b4f & 1) == 0 and b53 < 2 and not pend:
        ref = run(mk(v7, buf8=buf8, nk=nk, pend=True, f27_6=True, **kw)); kind = 'held_fire'
    else:
        ref = run(mk(v7, buf8=buf8, nk=nk, pend=pend, f27_6=f276, **kw)); kind = 'quiet'
    n[kind] += 1
    if snap(a) != snap(ref): bad.append((t, kind))
check('4000 random machine states match the exact specification (%s)' % n, not bad, str(bad[:4]))

# held key, fire: the CURRENT report reaches both endpoints unchanged
bad = []
for t in range(200):
    raw = [0xFF]*22; raw[rnd.randrange(22)] = 0xFE
    buf8 = [rnd.randrange(1, 256) for _ in range(8)]; nk = [4] + [rnd.randrange(256) for _ in range(15)]
    c = run(mk(v9, raw=raw, buf8=buf8, nk=nk, b4f=2, b53=0))
    ok = (bytes(c.xram[0xB48:0xB50]) == bytes(buf8) and c.xram[0xBA8] == 4 and bytes(c.xram[0xBA9:0xBB8]) == bytes(nk[1:])
          and bytes(c.iram[0x6C:0x74]) == bytes(buf8) and not c.bget(0x18) and (c.sfr[0xAA] & 4) and (c.sfr[0xAB] & 4) and c.sfr[0x81] == 0xC0)
    if not ok: bad.append(t)
check('key held: the current key report is re-sent unchanged on both endpoints (200 cases)', not bad, str(bad[:3]))
c = run(mk(v9, raw=[0xFE]+[0xFF]*21, buf8=[1]*8, nk=[4]+[1]*15, b4f=2, b53=0, pend=True, f27_6=True, aa=4, ab=4))
check('busy endpoint: report stays pending for retry', c.bget(0x18) and c.bget(0x3E) and c.pc == 0x5DA3)
c = mk(v9); c.pc = 0x5D9D; mx = 0xC0; s = 0
while c.pc != 0x5DA3 and s < 20000: c.step(); s += 1; mx = max(mx, c.sfr[0x81])
check('stack use unchanged (<= 2 extra bytes)', mx <= 0xC6, 'max SP %#x' % mx)
print('\nALL PASS' if not fails else '\nFAILED %s' % fails); sys.exit(1 if fails else 0)
