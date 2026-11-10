"""NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
 paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
usage: build_v8.py <stock_dump> <out.hex>
v8 = v7 (hardware-proven) + release guard.
Guard: once per sender tick (right before the 8-byte keyboard sender), if NO key is down (all 22 raw matrix columns 0xFF)
and the 10ms/1ms tick counters line up (about every 160 ms), and nothing is pending: zero the 8-byte and NKRO report
buffers and mark both pending, so an 'all keys up' report is (re)sent. Heals a lost key-release."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fwtools as fwio
import build_v7

CALL_SITE = 0x5D9D          # LCALL 8DAF  (12 8D AF)
CAVE = 0xA640
SEND8 = 0x8DAF


def assemble():
    code = bytearray()
    L = {}
    fix = []

    def emit(*b): code.extend(b)

    def lab(n): L[n] = len(code)

    def rel(op_bytes, target):          # emit op_bytes + rel8 placeholder
        emit(*op_bytes); fix.append((len(code), target)); emit(0)

    emit(0x78, 0x92)                     # MOV R0,#92h
    emit(0x7F, 0x16)                     # MOV R7,#16h
    lab('scan')
    emit(0xE6)                           # MOV A,@R0
    rel((0xB4, 0xFF), 'done')            # CJNE A,#FFh,done
    emit(0x08)                           # INC R0
    rel((0xDF,), 'scan')                 # DJNZ R7,scan
    emit(0xE5, 0x4F)                     # MOV A,4Fh
    emit(0x54, 0x0F)                     # ANL A,#0Fh
    rel((0x70,), 'done')                 # JNZ done
    emit(0xE5, 0x53)                     # MOV A,53h
    emit(0xC3)                           # CLR C
    emit(0x94, 0x02)                     # SUBB A,#2
    rel((0x50,), 'done')                 # JNC done
    rel((0x20, 0x18), 'done')            # JB 23h.0,done  (8-byte report already pending)
    emit(0x78, 0x6C, 0x7F, 0x08, 0xE4)   # R0=6Ch R7=8 CLR A
    lab('c1'); emit(0xF6, 0x08); rel((0xDF,), 'c1')      # MOV @R0,A ; INC R0 ; DJNZ R7,c1
    emit(0x78, 0x7E, 0x7F, 0x10, 0xE4)   # R0=7Eh R7=16 CLR A
    lab('c2'); emit(0xF6, 0x08); rel((0xDF,), 'c2')
    emit(0xD2, 0x18)                     # SETB 23h.0
    emit(0xD2, 0x3E)                     # SETB 27h.6
    lab('done')
    emit(0x02, SEND8 >> 8, SEND8 & 0xFF)  # LJMP 8DAF (it returns to the original caller)
    for pos, tgt in fix:
        d = L[tgt] - (pos + 1)
        assert -128 <= d <= 127, (tgt, d)
        code[pos] = d & 0xFF
    return bytes(code)


def build(stock_path):
    code = assemble()
    stock = fwio.load(stock_path)
    mem = bytearray(build_v7.build(stock))
    print('v7 sha256 (app region):', fwio.sha256_app(mem))
    assert bytes(mem[CALL_SITE:CALL_SITE + 3]) == bytes([0x12, 0x8D, 0xAF]), 'call site mismatch'
    fill = stock[CAVE]
    assert all(stock[CAVE + i] == fill and mem[CAVE + i] == fill for i in range(len(code) + 16)), 'cave area not free'
    out = bytearray(mem)
    out[CALL_SITE:CALL_SITE + 3] = bytes([0x12, CAVE >> 8, CAVE & 0xFF])
    out[CAVE:CAVE + len(code)] = code
    return mem, bytes(out), code


if __name__ == '__main__':
    mem, out, code = build(sys.argv[1])
    fwio.save_hex(sys.argv[2], out)
    print('guard length', len(code), 'bytes at %#x' % CAVE)
    print(code.hex(' '))
    diff = [i for i in range(fwio.APP_END) if mem[i] != out[i]]
    print(len(diff), 'bytes differ from v7:', hex(diff[0]), '..', hex(diff[-1]))
