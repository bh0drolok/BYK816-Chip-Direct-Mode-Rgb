#!/usr/bin/env python3
# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
"""Minimal 8051 disassembler + recursive-descent walker (library)."""

SFR = {
    0x80: "P0", 0x81: "SP", 0x82: "DPL", 0x83: "DPH", 0x87: "PCON",
    0x88: "TCON", 0x89: "TMOD", 0x8A: "TL0", 0x8B: "TL1", 0x8C: "TH0", 0x8D: "TH1",
    0x90: "P1", 0x98: "SCON", 0x99: "SBUF", 0xA0: "P2", 0xA8: "IE",
    0xB0: "P3", 0xB8: "IP", 0xD0: "PSW", 0xE0: "ACC", 0xF0: "B",
}


def dname(a):
    if a >= 0x80:
        return SFR.get(a, "SFR_%02X" % a)
    return "%02Xh" % a


def bname(b):
    if b < 0x80:
        return "%02Xh.%d" % (0x20 + (b >> 3), b & 7)
    return "%s.%d" % (dname(b & 0xF8), b & 7)


def s8(x):
    return x - 256 if x >= 128 else x


def decode(mem, pc):
    """return (length, text, kind, target); kind in None,'jmp','cjmp','call','ret','ijmp'"""
    op = mem[pc]
    b1 = mem[pc + 1] if pc + 1 < len(mem) else 0
    b2 = mem[pc + 2] if pc + 2 < len(mem) else 0
    lo = op & 0x0F
    hi = op >> 4

    def rel(n):
        return (pc + n + s8(mem[pc + n - 1])) & 0xFFFF

    if lo == 0x01:
        a11 = ((op >> 5) << 8) | b1
        tgt = ((pc + 2) & 0xF800) | a11
        if op & 0x10:
            return 2, "ACALL %04Xh" % tgt, "call", tgt
        return 2, "AJMP  %04Xh" % tgt, "jmp", tgt

    rn = "R%d" % (op & 7)
    ri = "@R%d" % (op & 1)

    if op == 0x00: return 1, "NOP", None, None
    if op == 0x02: t = (b1 << 8) | b2; return 3, "LJMP  %04Xh" % t, "jmp", t
    if op == 0x12: t = (b1 << 8) | b2; return 3, "LCALL %04Xh" % t, "call", t
    if op == 0x22: return 1, "RET", "ret", None
    if op == 0x32: return 1, "RETI", "ret", None
    if op == 0x73: return 1, "JMP   @A+DPTR", "ijmp", None
    if op == 0x80: t = rel(2); return 2, "SJMP  %04Xh" % t, "jmp", t
    if op == 0x10: t = rel(3); return 3, "JBC   %s,%04Xh" % (bname(b1), t), "cjmp", t
    if op == 0x20: t = rel(3); return 3, "JB    %s,%04Xh" % (bname(b1), t), "cjmp", t
    if op == 0x30: t = rel(3); return 3, "JNB   %s,%04Xh" % (bname(b1), t), "cjmp", t
    if op == 0x40: t = rel(2); return 2, "JC    %04Xh" % t, "cjmp", t
    if op == 0x50: t = rel(2); return 2, "JNC   %04Xh" % t, "cjmp", t
    if op == 0x60: t = rel(2); return 2, "JZ    %04Xh" % t, "cjmp", t
    if op == 0x70: t = rel(2); return 2, "JNZ   %04Xh" % t, "cjmp", t

    names = {0x2: "ADD", 0x3: "ADDC", 0x4: "ORL", 0x5: "ANL", 0x6: "XRL", 0x9: "SUBB"}
    if hi in names and lo >= 4:
        n = names[hi]
        if lo == 4: return 2, "%s   A,#%02Xh" % (n, b1), None, None
        if lo == 5: return 2, "%s   A,%s" % (n, dname(b1)), None, None
        if lo in (6, 7): return 1, "%s   A,%s" % (n, ri), None, None
        return 1, "%s   A,%s" % (n, rn), None, None
    if hi in (4, 5, 6) and lo == 2:
        n = {4: "ORL", 5: "ANL", 6: "XRL"}[hi]
        return 2, "%s   %s,A" % (n, dname(b1)), None, None
    if hi in (4, 5, 6) and lo == 3:
        n = {4: "ORL", 5: "ANL", 6: "XRL"}[hi]
        return 3, "%s   %s,#%02Xh" % (n, dname(b1), b2), None, None

    if op == 0x03: return 1, "RR    A", None, None
    if op == 0x13: return 1, "RRC   A", None, None
    if op == 0x23: return 1, "RL    A", None, None
    if op == 0x33: return 1, "RLC   A", None, None
    if op == 0x04: return 1, "INC   A", None, None
    if op == 0x14: return 1, "DEC   A", None, None
    if op == 0x05: return 2, "INC   %s" % dname(b1), None, None
    if op == 0x15: return 2, "DEC   %s" % dname(b1), None, None
    if op in (0x06, 0x07): return 1, "INC   %s" % ri, None, None
    if op in (0x16, 0x17): return 1, "DEC   %s" % ri, None, None
    if 0x08 <= op <= 0x0F: return 1, "INC   %s" % rn, None, None
    if 0x18 <= op <= 0x1F: return 1, "DEC   %s" % rn, None, None

    if op == 0x72: return 2, "ORL   C,%s" % bname(b1), None, None
    if op == 0x82: return 2, "ANL   C,%s" % bname(b1), None, None
    if op == 0xA0: return 2, "ORL   C,/%s" % bname(b1), None, None
    if op == 0xB0: return 2, "ANL   C,/%s" % bname(b1), None, None
    if op == 0x92: return 2, "MOV   %s,C" % bname(b1), None, None
    if op == 0xA2: return 2, "MOV   C,%s" % bname(b1), None, None
    if op == 0xB2: return 2, "CPL   %s" % bname(b1), None, None
    if op == 0xB3: return 1, "CPL   C", None, None
    if op == 0xC2: return 2, "CLR   %s" % bname(b1), None, None
    if op == 0xC3: return 1, "CLR   C", None, None
    if op == 0xD2: return 2, "SETB  %s" % bname(b1), None, None
    if op == 0xD3: return 1, "SETB  C", None, None

    if op == 0x74: return 2, "MOV   A,#%02Xh" % b1, None, None
    if op == 0x75: return 3, "MOV   %s,#%02Xh" % (dname(b1), b2), None, None
    if op in (0x76, 0x77): return 2, "MOV   %s,#%02Xh" % (ri, b1), None, None
    if 0x78 <= op <= 0x7F: return 2, "MOV   %s,#%02Xh" % (rn, b1), None, None
    if op == 0x83: return 1, "MOVC  A,@A+PC", None, None
    if op == 0x93: return 1, "MOVC  A,@A+DPTR", None, None
    if op == 0x84: return 1, "DIV   AB", None, None
    if op == 0xA4: return 1, "MUL   AB", None, None
    if op == 0x85: return 3, "MOV   %s,%s" % (dname(b2), dname(b1)), None, None
    if op in (0x86, 0x87): return 2, "MOV   %s,%s" % (dname(b1), ri), None, None
    if 0x88 <= op <= 0x8F: return 2, "MOV   %s,%s" % (dname(b1), rn), None, None
    if op == 0x90: return 3, "MOV   DPTR,#%04Xh" % ((b1 << 8) | b2), None, None
    if op == 0xA3: return 1, "INC   DPTR", None, None
    if op == 0xA5: return 1, "DB    0A5h", None, None
    if op in (0xA6, 0xA7): return 2, "MOV   %s,%s" % (ri, dname(b1)), None, None
    if 0xA8 <= op <= 0xAF: return 2, "MOV   %s,%s" % (rn, dname(b1)), None, None
    if op == 0xB4: t = rel(3); return 3, "CJNE  A,#%02Xh,%04Xh" % (b1, t), "cjmp", t
    if op == 0xB5: t = rel(3); return 3, "CJNE  A,%s,%04Xh" % (dname(b1), t), "cjmp", t
    if op in (0xB6, 0xB7): t = rel(3); return 3, "CJNE  %s,#%02Xh,%04Xh" % (ri, b1, t), "cjmp", t
    if 0xB8 <= op <= 0xBF: t = rel(3); return 3, "CJNE  %s,#%02Xh,%04Xh" % (rn, b1, t), "cjmp", t
    if op == 0xC0: return 2, "PUSH  %s" % dname(b1), None, None
    if op == 0xD0: return 2, "POP   %s" % dname(b1), None, None
    if op == 0xC4: return 1, "SWAP  A", None, None
    if op == 0xC5: return 2, "XCH   A,%s" % dname(b1), None, None
    if op in (0xC6, 0xC7): return 1, "XCH   A,%s" % ri, None, None
    if 0xC8 <= op <= 0xCF: return 1, "XCH   A,%s" % rn, None, None
    if op == 0xD4: return 1, "DA    A", None, None
    if op == 0xD5: t = rel(3); return 3, "DJNZ  %s,%04Xh" % (dname(b1), t), "cjmp", t
    if op in (0xD6, 0xD7): return 1, "XCHD  A,%s" % ri, None, None
    if 0xD8 <= op <= 0xDF: t = rel(2); return 2, "DJNZ  %s,%04Xh" % (rn, t), "cjmp", t
    if op == 0xE0: return 1, "MOVX  A,@DPTR", None, None
    if op in (0xE2, 0xE3): return 1, "MOVX  A,%s" % ri, None, None
    if op == 0xE4: return 1, "CLR   A", None, None
    if op == 0xE5: return 2, "MOV   A,%s" % dname(b1), None, None
    if op in (0xE6, 0xE7): return 1, "MOV   A,%s" % ri, None, None
    if 0xE8 <= op <= 0xEF: return 1, "MOV   A,%s" % rn, None, None
    if op == 0xF0: return 1, "MOVX  @DPTR,A", None, None
    if op in (0xF2, 0xF3): return 1, "MOVX  %s,A" % ri, None, None
    if op == 0xF4: return 1, "CPL   A", None, None
    if op == 0xF5: return 2, "MOV   %s,A" % dname(b1), None, None
    if op in (0xF6, 0xF7): return 1, "MOV   %s,A" % ri, None, None
    if 0xF8 <= op <= 0xFF: return 1, "MOV   %s,A" % rn, None, None
    return 1, "DB    %02Xh" % op, None, None


def walk(mem, entries, limit=0x10000):
    """recursive descent: returns dict pc -> (len, text, kind, target)"""
    seen = {}
    work = list(entries)
    while work:
        pc = work.pop()
        while 0 <= pc < limit and pc not in seen:
            ln, txt, kind, tgt = decode(mem, pc)
            seen[pc] = (ln, txt, kind, tgt)
            if kind in ("call", "cjmp") and tgt is not None:
                work.append(tgt)
            if kind == "jmp":
                if tgt is not None:
                    work.append(tgt)
                break
            if kind in ("ret", "ijmp"):
                break
            pc += ln
    return seen


VECTORS = [0x0000, 0x0003, 0x000B, 0x0013, 0x001B, 0x0023, 0x002B, 0x0033, 0x003B, 0x0043, 0x004B, 0x0053]


def show(mem, a, b, seen=None):
    pc = a
    while pc < b:
        ln, t, k, tg = decode(mem, pc)
        mark = "" if (seen is None or pc in seen) else "   ; (not reached)"
        print("%04X: %-10s %s%s" % (pc, mem[pc:pc + ln].hex(" "), t, mark))
        pc += ln
