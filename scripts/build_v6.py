#!/usr/bin/env python3
"""NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
 paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.

v6 'tiny report' patch for the Rapoo V720 (stock firmware dump).
New 6-byte feature report:  05 E0 <key idx> <R> <G> <B>   -> sets that key's colour directly in the LED buffers
(same buffers, same brightness scaling and same lock-key rule as the firmware's own painting renderer).
Nothing is written to flash; every other report/command behaves exactly as stock.
usage: build_v6.py <stock.bin> <out.bin>"""
import sys, hashlib
CAVE = 0xA500
S = 0x0130                   # 8 bytes of XRAM that the firmware never touches: S+0/1 offset, S+2 lock, S+3..5 B,G,R
def lj(a): return bytes([0x02, a >> 8, a & 0xFF])
def lc(a): return bytes([0x12, a >> 8, a & 0xFF])
def dptr(a): return bytes([0x90, a >> 8, a & 0xFF])

def build(stock):
    mem = bytearray(stock); changes = []
    def patch(addr, old, new, why):
        assert bytes(mem[addr:addr+len(old)]) == bytes(old), (hex(addr), mem[addr:addr+len(old)].hex())
        assert len(old) == len(new)
        mem[addr:addr+len(new)] = new; changes.append((addr, bytes(old), bytes(new), why))
    cave = bytearray()
    def here(): return CAVE + len(cave)
    def emit(*b): cave.extend(b)
    fix = []                                    # (pos_of_rel_byte, label)
    labels = {}
    def rel(label):
        fix.append((len(cave), label)); emit(0x00)
    afix=[]
    def far(label):
        afix.append((len(cave), label)); emit(0x02, 0, 0)
    def resolve():
        for pos, name in afix:
            a = labels[name]; cave[pos+1] = a >> 8; cave[pos+2] = a & 0xFF
        for pos, name in fix:
            d = labels[name] - (CAVE + pos + 1)
            assert -128 <= d <= 127, (name, d)
            cave[pos] = d & 0xFF

    # ---- scale: A = 0..255 colour -> R7/A = scaled by the brightness table, exactly like the stock renderer tail
    scale = here()
    emit(0xFD)                                   # MOV R5,A
    emit(0x7C, 0x00)                             # MOV R4,#0
    emit(0x78, 0xB7, 0xE6)                       # MOV R0,#B7h ; MOV A,@R0
    emit(*dptr(0x00EE)); emit(0x93)              # MOV DPTR,#00EEh ; MOVC A,@A+DPTR
    emit(0xFF)                                   # MOV R7,A
    emit(0x7E, 0x00)                             # MOV R6,#0
    emit(*lc(0x5534))
    emit(0x7C, 0x00, 0x7D, 0x0A)                 # MOV R4,#0 ; MOV R5,#0Ah
    emit(*lc(0x5546))
    emit(0xEF, 0x22)                             # MOV A,R7 ; RET

    # ---- hook entered from 5358 (generic fall-through of the 6-byte report handler)
    hook = here()
    emit(0x78, 0x04, 0xE2, 0xFE, 0x08, 0xE2, 0xF5, 0x82, 0x8E, 0x83)   # DPTR = report buffer pointer ([04],[05])
    emit(0xE0, 0x64, 0x05); emit(0x60, 0x03); far('orig')                       # byte0 must be 05
    emit(0xA3, 0xE0, 0xB4, 0xE0, 0x02, 0x80, 0x03); far('orig')                             # byte1 must be E0
    emit(0xA3, 0xE0, 0xFA)                                                # idx -> R2
    emit(0xA3, 0xE0, 0xC0, 0xE0)                                          # R  -> push
    emit(0xA3, 0xE0, 0xC0, 0xE0)                                          # G  -> push
    emit(0xA3, 0xE0, 0xC0, 0xE0)                                          # B  -> push
    emit(*dptr(S + 3)); emit(0xD0, 0xE0, 0xF0)                            # pop B -> S+3
    emit(*dptr(S + 4)); emit(0xD0, 0xE0, 0xF0)                            # pop G -> S+4
    emit(*dptr(S + 5)); emit(0xD0, 0xE0, 0xF0)                            # pop R -> S+5
    # idx must be < 132
    emit(0xEA, 0xC3, 0x94, 0x84); emit(0x40, 0x03); far('done')                 # MOV A,R2 ; CLR C ; SUBB A,#84h ; JNC done
    # T1 = [0CF1+idx] -> R6 ; T2 = [0D75+idx] -> R5
    emit(*dptr(0x0CF1)); emit(0xEA, 0x25, 0x82, 0xF5, 0x82, 0xE4, 0x35, 0x83, 0xF5, 0x83, 0xE4, 0x93, 0xFE)
    emit(*dptr(0x0D75)); emit(0xEA, 0x25, 0x82, 0xF5, 0x82, 0xE4, 0x35, 0x83, 0xF5, 0x83, 0xE4, 0x93, 0xFD)
    emit(0xEE, 0xC3, 0x94, 0x16); emit(0x40, 0x03); far('done')                 # T1 >= 0x16 -> no such key
    # offset = T1*0x12 + T2*3  -> S+0 (hi), S+1 (lo)
    emit(0xEE, 0x75, 0xF0, 0x12, 0xA4, 0xFB, 0xAA, 0xF0)                  # MOV A,R6 ; MOV B,#12h ; MUL AB ; MOV R3,A ; MOV R2,B
    emit(0xED, 0x75, 0xF0, 0x03, 0xA4, 0x2B, 0xFB, 0xE4, 0x3A, 0xFA)      # A=R5*3 ; ADD A,R3 ; MOV R3,A ; CLR A ; ADDC A,R2 ; MOV R2,A
    emit(*dptr(S)); emit(0xEA, 0xF0, 0xA3, 0xEB, 0xF0)                    # S+0=R2 ; S+1=R3
    # lock-key rule (stock: 96BD(R7=T2, R5=T1) != 0 -> keep the arrays untouched)
    emit(0xED, 0xFF, 0xEE, 0xFD)                                          # MOV A,R5 ; MOV R7,A ; MOV A,R6 ; MOV R5,A
    emit(*lc(0x96BD))
    emit(*dptr(S + 2)); emit(0xEF, 0xF0)                                  # S+2 = R7
    for ch in range(3):
        emit(*dptr(S + 3 + ch)); emit(0xE0)                               # A = colour (ch0=B,ch1=G,ch2=R)
        emit(*lc(scale))                                                  # A,R7 = scaled
        emit(*dptr(S)); emit(0xE0, 0xFA, 0xA3, 0xE0, 0xFB)                # R2 = hi, R3 = lo (A = lo)
        emit(0x24, (0x86 + ch) & 0xFF, 0xF5, 0x82, 0xEA, 0x34, 0x03, 0xF5, 0x83, 0xEF, 0xF0)   # live[0386+off+ch] = R7
        emit(*dptr(S + 2)); emit(0xE0); emit(0x70); rel('skip%d' % ch)    # lock != 0 -> skip arrays
        emit(0xEB, 0x24, (0xD9 + ch) & 0xFF, 0xF5, 0x82, 0xEA, 0x34, 0x01, 0xF5, 0x83, 0xEF, 0xF0)   # arr[01D9+off+ch] = R7
        labels['skip%d' % ch] = here()
    labels['done'] = here()
    emit(0xE4, 0xF5, 0x46)                                                # CLR A ; MOV 46h,A  (report finished)
    emit(*lj(0x5480))
    labels['orig'] = here()
    emit(0x78, 0x04, 0xE2)                                                # original 5358..535A
    emit(*lj(0x535B))
    resolve()
    assert here() <= CAVE + 0x300, hex(here())
    assert all(b == 0 for b in mem[CAVE:CAVE+len(cave)])
    old = bytes(mem[CAVE:CAVE+len(cave)]); mem[CAVE:CAVE+len(cave)] = cave
    changes.append((CAVE, old, bytes(cave), "new code in unused (all-zero) flash"))
    patch(0x5358, mem[0x5358:0x535B], lj(hook), "6-byte report handler: jump to hook (05 E0 idx R G B sets one key, anything else as stock)")
    return bytes(mem), changes, dict(scale=scale, hook=hook, end=here())

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
