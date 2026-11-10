#!/usr/bin/env python3
# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
"""Small 8051 interpreter (library) for testing firmware patches.
code: bytes (64K), xram: bytearray(64K). @Ri MOVX uses XPAGE (SFR F7) as high byte."""

ACC, B, PSW, SP, DPL, DPH, XPAGE, IE = 0xE0, 0xF0, 0xD0, 0x81, 0x82, 0x83, 0xF7, 0xA8


class CPU:
    def __init__(self, code, xram=None):
        self.code = bytes(code)
        self.xram = xram if xram is not None else bytearray(0x10000)
        self.iram = bytearray(256)
        self.sfr = {}
        self.pc = 0
        self.sfr[SP] = 7
        self.steps = 0

    # ---- helpers
    def rs(self, a):
        return self.sfr.get(a, 0)

    @property
    def a(self):
        return self.rs(ACC)

    @a.setter
    def a(self, v):
        self.sfr[ACC] = v & 0xFF

    @property
    def dptr(self):
        return (self.rs(DPH) << 8) | self.rs(DPL)

    @dptr.setter
    def dptr(self, v):
        v &= 0xFFFF
        self.sfr[DPH] = v >> 8
        self.sfr[DPL] = v & 0xFF

    def reg(self, n):
        return ((self.rs(PSW) >> 3) & 3) * 8 + n

    def getr(self, n):
        return self.iram[self.reg(n)]

    def setr(self, n, v):
        self.iram[self.reg(n)] = v & 0xFF

    @property
    def c(self):
        return (self.rs(PSW) >> 7) & 1

    @c.setter
    def c(self, v):
        p = self.rs(PSW)
        self.sfr[PSW] = (p | 0x80) if v else (p & 0x7F)

    def dget(self, d):
        if d < 0x80:
            return self.iram[d]
        return self.rs(d)

    def dset(self, d, v):
        v &= 0xFF
        if d < 0x80:
            self.iram[d] = v
        else:
            self.sfr[d] = v

    def iget(self, i):
        return self.iram[i & 0xFF]

    def iset(self, i, v):
        self.iram[i & 0xFF] = v & 0xFF

    def bget(self, b):
        if b < 0x80:
            return (self.iram[0x20 + (b >> 3)] >> (b & 7)) & 1
        return (self.rs(b & 0xF8) >> (b & 7)) & 1

    def bset(self, b, v):
        if b < 0x80:
            ad = 0x20 + (b >> 3)
            m = 1 << (b & 7)
            self.iram[ad] = (self.iram[ad] | m) if v else (self.iram[ad] & ~m & 0xFF)
        else:
            ad = b & 0xF8
            m = 1 << (b & 7)
            cur = self.rs(ad)
            self.sfr[ad] = (cur | m) if v else (cur & ~m & 0xFF)

    def push(self, v):
        sp = (self.rs(SP) + 1) & 0xFF
        self.sfr[SP] = sp
        self.iram[sp] = v & 0xFF

    def pop(self):
        sp = self.rs(SP)
        v = self.iram[sp]
        self.sfr[SP] = (sp - 1) & 0xFF
        return v

    def xri(self, i):  # MOVX @Ri address
        return (self.rs(XPAGE) << 8) | self.getr(i)

    # ---- ALU
    def add(self, v, carry=0):
        a = self.a
        r = a + v + carry
        self.c = r > 0xFF
        self.a = r

    def subb(self, v):
        a = self.a
        r = a - v - self.c
        self.c = r < 0
        self.a = r

    def operand(self, op, pc):
        """returns (value, length) for ALU group low nibble 4..F"""
        lo = op & 0xF
        code = self.code
        if lo == 4:
            return code[pc + 1], 2
        if lo == 5:
            return self.dget(code[pc + 1]), 2
        if lo in (6, 7):
            return self.iget(self.getr(lo - 6)), 1
        return self.getr(lo - 8), 1

    def rel(self, pc, n, off_idx):
        o = self.code[pc + off_idx]
        o = o - 256 if o > 127 else o
        return (pc + n + o) & 0xFFFF

    def step(self):
        code = self.code
        pc = self.pc
        op = code[pc]
        hi, lo = op >> 4, op & 0xF
        self.steps += 1
        nxt = pc + 1

        # ALU groups
        if hi in (2, 3, 9) and lo >= 4:
            v, ln = self.operand(op, pc)
            if hi == 2:
                self.add(v)
            elif hi == 3:
                self.add(v, self.c)
            else:
                self.subb(v)
            self.pc = pc + ln
            return
        if hi in (4, 5, 6) and lo >= 4:
            v, ln = self.operand(op, pc)
            f = {4: lambda x, y: x | y, 5: lambda x, y: x & y, 6: lambda x, y: x ^ y}[hi]
            self.a = f(self.a, v)
            self.pc = pc + ln
            return
        if hi in (4, 5, 6) and lo in (2, 3):
            f = {4: lambda x, y: x | y, 5: lambda x, y: x & y, 6: lambda x, y: x ^ y}[hi]
            d = code[pc + 1]
            if lo == 2:
                self.dset(d, f(self.dget(d), self.a))
                self.pc = pc + 2
            else:
                self.dset(d, f(self.dget(d), code[pc + 2]))
                self.pc = pc + 3
            return

        if op == 0x00:
            self.pc = nxt
        elif lo == 1:  # AJMP / ACALL
            a11 = ((op >> 5) << 8) | code[pc + 1]
            t = ((pc + 2) & 0xF800) | a11
            if op & 0x10:
                r = pc + 2
                self.push(r & 0xFF)
                self.push(r >> 8)
            self.pc = t
        elif op == 0x02:
            self.pc = (code[pc + 1] << 8) | code[pc + 2]
        elif op == 0x12:
            r = pc + 3
            self.push(r & 0xFF)
            self.push(r >> 8)
            self.pc = (code[pc + 1] << 8) | code[pc + 2]
        elif op in (0x22, 0x32):
            h = self.pop()
            l = self.pop()
            self.pc = (h << 8) | l
        elif op == 0x03:
            a = self.a
            self.a = ((a >> 1) | (a << 7)) & 0xFF
            self.pc = nxt
        elif op == 0x13:
            a = self.a
            c = self.c
            self.c = a & 1
            self.a = (a >> 1) | (c << 7)
            self.pc = nxt
        elif op == 0x23:
            a = self.a
            self.a = ((a << 1) | (a >> 7)) & 0xFF
            self.pc = nxt
        elif op == 0x33:
            a = self.a
            c = self.c
            self.c = (a >> 7) & 1
            self.a = ((a << 1) | c) & 0xFF
            self.pc = nxt
        elif op == 0x04:
            self.a = self.a + 1
            self.pc = nxt
        elif op == 0x14:
            self.a = self.a - 1
            self.pc = nxt
        elif op == 0x05:
            d = code[pc + 1]
            self.dset(d, self.dget(d) + 1)
            self.pc = pc + 2
        elif op == 0x15:
            d = code[pc + 1]
            self.dset(d, self.dget(d) - 1)
            self.pc = pc + 2
        elif op in (0x06, 0x07):
            i = self.getr(op & 1)
            self.iset(i, self.iget(i) + 1)
            self.pc = nxt
        elif op in (0x16, 0x17):
            i = self.getr(op & 1)
            self.iset(i, self.iget(i) - 1)
            self.pc = nxt
        elif 0x08 <= op <= 0x0F:
            self.setr(lo - 8, self.getr(lo - 8) + 1)
            self.pc = nxt
        elif 0x18 <= op <= 0x1F:
            self.setr(lo - 8, self.getr(lo - 8) - 1)
            self.pc = nxt
        elif op == 0x10:  # JBC
            b = code[pc + 1]
            t = self.rel(pc, 3, 2)
            if self.bget(b):
                self.bset(b, 0)
                self.pc = t
            else:
                self.pc = pc + 3
        elif op == 0x20:
            t = self.rel(pc, 3, 2)
            self.pc = t if self.bget(code[pc + 1]) else pc + 3
        elif op == 0x30:
            t = self.rel(pc, 3, 2)
            self.pc = t if not self.bget(code[pc + 1]) else pc + 3
        elif op == 0x40:
            self.pc = self.rel(pc, 2, 1) if self.c else pc + 2
        elif op == 0x50:
            self.pc = self.rel(pc, 2, 1) if not self.c else pc + 2
        elif op == 0x60:
            self.pc = self.rel(pc, 2, 1) if self.a == 0 else pc + 2
        elif op == 0x70:
            self.pc = self.rel(pc, 2, 1) if self.a != 0 else pc + 2
        elif op == 0x80:
            self.pc = self.rel(pc, 2, 1)
        elif op == 0x72:
            self.c = self.c | self.bget(code[pc + 1])
            self.pc = pc + 2
        elif op == 0x82:
            self.c = self.c & self.bget(code[pc + 1])
            self.pc = pc + 2
        elif op == 0xA0:
            self.c = self.c | (1 - self.bget(code[pc + 1]))
            self.pc = pc + 2
        elif op == 0xB0:
            self.c = self.c & (1 - self.bget(code[pc + 1]))
            self.pc = pc + 2
        elif op == 0x92:
            self.bset(code[pc + 1], self.c)
            self.pc = pc + 2
        elif op == 0xA2:
            self.c = self.bget(code[pc + 1])
            self.pc = pc + 2
        elif op == 0xB2:
            b = code[pc + 1]
            self.bset(b, 1 - self.bget(b))
            self.pc = pc + 2
        elif op == 0xB3:
            self.c = 1 - self.c
            self.pc = nxt
        elif op == 0xC2:
            self.bset(code[pc + 1], 0)
            self.pc = pc + 2
        elif op == 0xC3:
            self.c = 0
            self.pc = nxt
        elif op == 0xD2:
            self.bset(code[pc + 1], 1)
            self.pc = pc + 2
        elif op == 0xD3:
            self.c = 1
            self.pc = nxt
        elif op == 0x73:
            self.pc = (self.dptr + self.a) & 0xFFFF
        elif op == 0x74:
            self.a = code[pc + 1]
            self.pc = pc + 2
        elif op == 0x75:
            self.dset(code[pc + 1], code[pc + 2])
            self.pc = pc + 3
        elif op in (0x76, 0x77):
            self.iset(self.getr(op & 1), code[pc + 1])
            self.pc = pc + 2
        elif 0x78 <= op <= 0x7F:
            self.setr(lo - 8, code[pc + 1])
            self.pc = pc + 2
        elif op == 0x83:
            self.a = code[(pc + 1 + self.a) & 0xFFFF]
            self.pc = nxt
        elif op == 0x93:
            self.a = code[(self.dptr + self.a) & 0xFFFF]
            self.pc = nxt
        elif op == 0x84:
            a, b = self.a, self.rs(B)
            if b == 0:
                self.sfr[PSW] = self.rs(PSW) | 0x04
            else:
                self.a = a // b
                self.sfr[B] = a % b
                self.sfr[PSW] = self.rs(PSW) & ~0x04
            self.c = 0
            self.pc = nxt
        elif op == 0xA4:
            r = self.a * self.rs(B)
            self.a = r & 0xFF
            self.sfr[B] = r >> 8
            self.c = 0
            self.pc = nxt
        elif op == 0x85:
            self.dset(code[pc + 2], self.dget(code[pc + 1]))
            self.pc = pc + 3
        elif op in (0x86, 0x87):
            self.dset(code[pc + 1], self.iget(self.getr(op & 1)))
            self.pc = pc + 2
        elif 0x88 <= op <= 0x8F:
            self.dset(code[pc + 1], self.getr(lo - 8))
            self.pc = pc + 2
        elif op == 0x90:
            self.dptr = (code[pc + 1] << 8) | code[pc + 2]
            self.pc = pc + 3
        elif op == 0xA3:
            self.dptr = self.dptr + 1
            self.pc = nxt
        elif op in (0xA6, 0xA7):
            self.iset(self.getr(op & 1), self.dget(code[pc + 1]))
            self.pc = pc + 2
        elif 0xA8 <= op <= 0xAF:
            self.setr(lo - 8, self.dget(code[pc + 1]))
            self.pc = pc + 2
        elif op == 0xB4:
            v = code[pc + 1]
            self.c = self.a < v
            self.pc = self.rel(pc, 3, 2) if self.a != v else pc + 3
        elif op == 0xB5:
            v = self.dget(code[pc + 1])
            self.c = self.a < v
            self.pc = self.rel(pc, 3, 2) if self.a != v else pc + 3
        elif op in (0xB6, 0xB7):
            x = self.iget(self.getr(op & 1))
            v = code[pc + 1]
            self.c = x < v
            self.pc = self.rel(pc, 3, 2) if x != v else pc + 3
        elif 0xB8 <= op <= 0xBF:
            x = self.getr(lo - 8)
            v = code[pc + 1]
            self.c = x < v
            self.pc = self.rel(pc, 3, 2) if x != v else pc + 3
        elif op == 0xC0:
            self.push(self.dget(code[pc + 1]))
            self.pc = pc + 2
        elif op == 0xD0:
            self.dset(code[pc + 1], self.pop())
            self.pc = pc + 2
        elif op == 0xC4:
            a = self.a
            self.a = ((a << 4) | (a >> 4)) & 0xFF
            self.pc = nxt
        elif op == 0xC5:
            d = code[pc + 1]
            t = self.dget(d)
            self.dset(d, self.a)
            self.a = t
            self.pc = pc + 2
        elif op in (0xC6, 0xC7):
            i = self.getr(op & 1)
            t = self.iget(i)
            self.iset(i, self.a)
            self.a = t
            self.pc = nxt
        elif 0xC8 <= op <= 0xCF:
            t = self.getr(lo - 8)
            self.setr(lo - 8, self.a)
            self.a = t
            self.pc = nxt
        elif op == 0xD5:
            d = code[pc + 1]
            v = (self.dget(d) - 1) & 0xFF
            self.dset(d, v)
            self.pc = self.rel(pc, 3, 2) if v != 0 else pc + 3
        elif 0xD8 <= op <= 0xDF:
            v = (self.getr(lo - 8) - 1) & 0xFF
            self.setr(lo - 8, v)
            self.pc = self.rel(pc, 2, 1) if v != 0 else pc + 2
        elif op in (0xD6, 0xD7):
            i = self.getr(op & 1)
            x = self.iget(i)
            a = self.a
            self.iset(i, (x & 0xF0) | (a & 0x0F))
            self.a = (a & 0xF0) | (x & 0x0F)
            self.pc = nxt
        elif op == 0xE0:
            self.a = self.xram[self.dptr]
            self.pc = nxt
        elif op in (0xE2, 0xE3):
            self.a = self.xram[self.xri(op & 1)]
            self.pc = nxt
        elif op == 0xE4:
            self.a = 0
            self.pc = nxt
        elif op == 0xE5:
            self.a = self.dget(code[pc + 1])
            self.pc = pc + 2
        elif op in (0xE6, 0xE7):
            self.a = self.iget(self.getr(op & 1))
            self.pc = nxt
        elif 0xE8 <= op <= 0xEF:
            self.a = self.getr(lo - 8)
            self.pc = nxt
        elif op == 0xF0:
            self.xram[self.dptr] = self.a
            self.pc = nxt
        elif op in (0xF2, 0xF3):
            self.xram[self.xri(op & 1)] = self.a
            self.pc = nxt
        elif op == 0xF4:
            self.a = ~self.a
            self.pc = nxt
        elif op == 0xF5:
            self.dset(code[pc + 1], self.a)
            self.pc = pc + 2
        elif op in (0xF6, 0xF7):
            self.iset(self.getr(op & 1), self.a)
            self.pc = nxt
        elif 0xF8 <= op <= 0xFF:
            self.setr(lo - 8, self.a)
            self.pc = nxt
        else:
            raise RuntimeError("unsupported opcode %02X at %04X" % (op, pc))

    def run(self, until, limit=2_000_000):
        """until: set of pc values at which to stop BEFORE executing"""
        for _ in range(limit):
            if self.pc in until:
                return self.pc
            self.step()
        raise RuntimeError("step limit; pc=%04X" % self.pc)
