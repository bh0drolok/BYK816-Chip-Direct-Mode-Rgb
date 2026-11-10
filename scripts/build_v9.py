"""NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
 paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
usage: build_v9.py <stock_dump> <out.hex>
v9 = v7 (hardware-proven) + report guard:
   * no key down (all 22 raw matrix columns 0xFF), ~every 160 ms : clear report buffers, resend 'all up'   (v8 behaviour, cures stuck keys)
   * key(s) down, ~every 20 ms                                     : resend the CURRENT report as it is      (new: heals a lost key-press report)
Both only ever set the firmware's own 'report pending' flags; the firmware's own senders do the transmitting."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fwtools as fwio
import build_v7
CALL_SITE = 0x5D9D
CAVE = 0xA640
SEND8 = 0x8DAF

def assemble():
    code = bytearray(); L = {}; fix = []
    def emit(*b): code.extend(b)
    def lab(n): L[n] = len(code)
    def rel(op, t): emit(*op); fix.append((len(code), t)); emit(0)
    emit(0x78, 0x92); emit(0x7F, 0x16)                   # R0=#92h (raw matrix), R7=22 columns
    lab('scan'); emit(0xE6)                              # MOV A,@R0
    rel((0xB4, 0xFF), 'held')                            # CJNE A,#FFh,held   (some key is down)
    emit(0x08); rel((0xDF,), 'scan')                     # INC R0 ; DJNZ R7,scan
    # ---- idle: all keys up -------------------------------------------------------------------------------
    emit(0xE5, 0x4F); emit(0x54, 0x0F); rel((0x70,), 'done')      # (4Fh & 0Fh)==0   ~160 ms
    emit(0xE5, 0x53); emit(0xC3); emit(0x94, 0x02); rel((0x50,), 'done')   # 53h < 2
    rel((0x20, 0x18), 'done')                            # JB 23h.0 (already pending)
    emit(0x78, 0x6C, 0x7F, 0x08, 0xE4)                   # clear 8-byte report buffer
    lab('c1'); emit(0xF6, 0x08); rel((0xDF,), 'c1')
    emit(0x78, 0x7E, 0x7F, 0x10, 0xE4)                   # clear NKRO report buffer
    lab('c2'); emit(0xF6, 0x08); rel((0xDF,), 'c2')
    emit(0xD2, 0x18); emit(0xD2, 0x3E)                   # SETB 23h.0 ; SETB 27h.6
    rel((0x80,), 'done')                                 # SJMP done
    # ---- held: some key down -----------------------------------------------------------------------------
    lab('held')
    emit(0xE5, 0x4F); rel((0x20, 0xE0), 'done')          # JB ACC.0,done     (every other 10 ms tick ~ 20 ms)
    emit(0xE5, 0x53); emit(0xC3); emit(0x94, 0x02); rel((0x50,), 'done')   # 53h < 2
    rel((0x20, 0x18), 'done')                            # JB 23h.0 (already pending)
    emit(0xD2, 0x18); emit(0xD2, 0x3E)                   # resend the current reports unchanged
    lab('done'); emit(0x02, SEND8 >> 8, SEND8 & 0xFF)    # LJMP 8DAF
    for pos, tgt in fix:
        d = L[tgt] - (pos + 1); assert -128 <= d <= 127, (tgt, d); code[pos] = d & 0xFF
    return bytes(code)

def build(stock_path):
    stock = fwio.load(stock_path)
    mem = bytearray(build_v7.build(stock))
    # known-good v7 hex FILE sha256 (research keyboard's dump; the app-region hash printed below differs): 88c99b84f75eb9a2882c7e8ac8d5948bc8bbcb9a1a7bdbdd9deafb7957fd9ac3
    print('v7 sha256 (app region):', fwio.sha256_app(mem))
    code = assemble()
    assert bytes(mem[CALL_SITE:CALL_SITE + 3]) == bytes([0x12, 0x8D, 0xAF])
    fill = stock[CAVE]
    assert all(stock[CAVE + i] == fill and mem[CAVE + i] == fill for i in range(len(code) + 16))
    out = bytearray(mem)
    out[CALL_SITE:CALL_SITE + 3] = bytes([0x12, CAVE >> 8, CAVE & 0xFF])
    out[CAVE:CAVE + len(code)] = code
    return mem, bytes(out), code

if __name__ == '__main__':
    mem, out, code = build(sys.argv[1])
    fwio.save_hex(sys.argv[2], out)
    diff = [i for i in range(fwio.APP_END) if mem[i] != out[i]]
    print('guard', len(code), 'bytes at %#x; %d bytes differ from v7' % (CAVE, len(diff)))
    print(code.hex(' '))
