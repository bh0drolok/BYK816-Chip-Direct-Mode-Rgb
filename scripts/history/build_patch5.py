#!/usr/bin/env python3
# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
"""v5 = v3 + tagged frames repaint layer 0 in place (no clear, no effect restart). Original v3 doc: 'streamed frame' patch for the Rapoo V720 (stock firmware dump).
Idea: a host frame (06 09 AC 00 ...) whose payload carries the 4-byte tag 'RT2' marker at payload offset 0x318
stays in the USB staging buffer (XRAM 05D1..09D0) and is NOT erased/programmed into flash. The layer-0 renderer
reads its 3 colour planes from the staging buffer while that tag is present, else from flash (stock behaviour).
No extra RAM is used.  usage: build_patch3.py <stock.bin> <out.bin>"""
import sys, hashlib
CAVE = 0xA500
TAGADDR = 0x05D1 + 0x318          # 0x08E9
TAG = bytes([0x52, 0x54, 0x56, 0x32])   # 'RTV2'
DELTA = 0xAC00 - 0x05D1           # 0xA62F : flash page AC00 -> staging 05D1
def lj(a): return bytes([0x02, a >> 8, a & 0xFF])
def lc(a): return bytes([0x12, a >> 8, a & 0xFF])

def build(stock):
    mem = bytearray(stock); changes = []
    def patch(addr, old, new, why):
        assert bytes(mem[addr:addr+len(old)]) == bytes(old), (hex(addr), mem[addr:addr+len(old)].hex())
        assert len(old) == len(new)
        mem[addr:addr+len(new)] = new; changes.append((addr, bytes(old), bytes(new), why))
    cave = bytearray()
    def here(): return CAVE + len(cave)
    def emit(*b): cave.extend(b)
    fixups = []
    def jne(label_name):               # placeholder rel for CJNE ... , label
        fixups.append((len(cave) - 1, label_name))
    labels = {}
    def resolve():
        for pos, name in fixups:
            d = labels[name] - (CAVE + pos + 1)
            assert -128 <= d <= 127, (name, d)
            cave[pos] = d & 0xFF
    def tagcheck(fail):                # DPTR=TAGADDR already; compare 4 bytes, jump to `fail` on mismatch
        for i, t in enumerate(TAG):
            if i: emit(0xA3)           # INC DPTR
            emit(0xE0)                 # MOVX A,@DPTR
            emit(0xB4, t, 0x00); jne(fail)   # CJNE A,#t,fail

    # ---- rd: read plane byte. in DPTR = flash address (AC00..AE..), out A = byte (RAM if tag, else flash MOVC)
    rd = here(); labels['rd'] = rd
    emit(0xC0, 0x83, 0xC0, 0x82)                          # PUSH DPH ; PUSH DPL
    emit(0x90, TAGADDR >> 8, TAGADDR & 0xFF)             # MOV DPTR,#TAGADDR
    tagcheck('rd_flash')
    emit(0xD0, 0x82, 0xD0, 0x83)                          # POP DPL ; POP DPH
    emit(0xC3, 0xE5, 0x82, 0x94, DELTA & 0xFF, 0xF5, 0x82)          # CLR C ; MOV A,DPL ; SUBB A,#2F ; MOV DPL,A
    emit(0xE5, 0x83, 0x94, DELTA >> 8, 0xF5, 0x83)                  # MOV A,DPH ; SUBB A,#A6 ; MOV DPH,A
    emit(0xE0, 0x22)                                                # MOVX A,@DPTR ; RET
    labels['rd_flash'] = here()
    emit(0xD0, 0x82, 0xD0, 0x83, 0xE4, 0x93, 0x22)        # POP DPL ; POP DPH ; CLR A ; MOVC A,@A+DPTR ; RET

    stub3 = here(); emit(*lc(rd), 0xFB, 0x22)             # LCALL rd ; MOV R3,A ; RET
    stub5 = here(); emit(*lc(rd), 0xFD, 0x22)             # LCALL rd ; MOV R5,A ; RET
    c3 = here()                                           # layer-0 plane 3 tail (copy of 26AD..26B3 + rd)
    emit(0xF5, 0x82, 0xE4, 0x35, 0x83, 0xF5, 0x83)
    emit(*lc(rd), 0xFD)
    emit(*lj(0x26B7))

    # ---- hook2 at 9DE0 (host page write): tagged frame for page AC, type 9 -> keep in RAM, skip flash
    hook2 = here()
    emit(0xC0, 0xE0, 0xC0, 0x83, 0xC0, 0x82)             # PUSH ACC, DPH, DPL
    emit(0xE5, 0x49); emit(0xB4, 0xAC, 0x00); jne('orig2')     # page high byte == AC ?
    emit(0xE5, 0x48); emit(0xB4, 0x09, 0x00); jne('orig2')     # report type == 9 ?
    emit(0x90, TAGADDR >> 8, TAGADDR & 0xFF)
    tagcheck('orig2')
    emit(0xD0, 0x82, 0xD0, 0x83, 0xD0, 0xE0, 0x22)       # POP DPL, DPH, ACC ; RET  (flash write skipped)
    labels['orig2'] = here()
    emit(0xD0, 0x82, 0xD0, 0x83, 0xD0, 0xE0)
    emit(0xA2, 0xAF, 0x92, 0x54)                          # original: MOV C,IE.7 ; MOV 2Ah.4,C
    emit(*lj(0x9DE4))

    # ---- hook0 at 545E (type-9 dispatch): original = SETB 20.1; SETB 27.1; CLR A; MOV DPTR,#0512; MOVX @DPTR,A
    hook0 = here()
    emit(0xE5, 0x49); emit(0xB4, 0xAC, 0x00); jne('orig0')     # page AC ?
    emit(0x90, TAGADDR >> 8, TAGADDR & 0xFF)
    tagcheck('orig0')
    # tagged: paint layer 0 straight into the live LED buffer WITHOUT the stock clear-first step
    emit(0xC2, 0x05)                                     # CLR 20.5            (as 24CF does)
    emit(0xE4, 0x78, 0x25, 0xF2)                         # CLR A ; MOV R0,#25h ; MOVX @R0,A   layer = 0
    emit(0x78, 0x26, 0xF2)                               # MOV R0,#26h ; MOVX @R0,A            row = 0
    emit(*lc(0x24DC))                                    # LCALL 24DC (row/col render loop; RET after row 5)
    emit(*lj(0x5467))
    labels['orig0'] = here()
    emit(0xD2, 0x01, 0xD2, 0x39)                         # SETB 20.1 ; SETB 27.1  (stock)
    emit(0xE4, 0x90, 0x05, 0x12, 0xF0)                   # CLR A ; MOV DPTR,#0512 ; MOVX @DPTR,A  (stock)
    emit(*lj(0x5467))
    resolve()
    assert here() <= CAVE + 0x100, hex(here())
    assert all(b == 0 for b in mem[CAVE:CAVE+len(cave)])
    old = bytes(mem[CAVE:CAVE+len(cave)]); mem[CAVE:CAVE+len(cave)] = cave
    changes.append((CAVE, old, bytes(cave), "new code in unused (all-zero) flash"))
    patch(0x9DE0, mem[0x9DE0:0x9DE3], lj(hook2), "host page-write routine -> hook (tagged AC frame stays in RAM)")
    patch(0x545E, mem[0x545E:0x5461], lj(hook0), "type-9 dispatch -> hook0 (tagged frame: in-place layer-0 repaint, no clear, no effect restart)")
    patch(0x250C, bytes([0xE4, 0x93, 0xFB]), lc(stub3), "layer0 plane1 read: CLR A;MOVC;MOV R3,A -> LCALL (RAM if tag else flash)")
    patch(0x252A, bytes([0xE4, 0x93, 0xFD]), lc(stub5), "layer0 plane2 read: CLR A;MOVC;MOV R5,A -> LCALL (RAM if tag else flash)")
    patch(0x2543, mem[0x2543:0x2546], lj(c3), "layer0 plane3 read: jump to tail (RAM if tag else flash)")
    return bytes(mem), changes, dict(rd=rd, stub3=stub3, stub5=stub5, c3=c3, hook2=hook2, hook0=hook0, end=here())

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
