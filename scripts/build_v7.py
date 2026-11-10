#!/usr/bin/env python3
"""build_v7.py - v7 = v6 builder with brightness scaling disabled (hardware-proven version).
NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
 paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.

v7 is exactly the v6 image with the first two bytes of the 'scale' helper in the code cave (0xA500) changed
from  FD 7C  (MOV R5,A / MOV R4,#0 ...)  to  FF 22  (MOV R7,A / RET), so a colour is stored as given.
usage: build_v7.py <stock_dump.bin|.hex> <out.hex>"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fwtools, build_v6

def build(stock):
    out, changes, addrs = build_v6.build(bytes(stock))
    m = bytearray(out)
    assert bytes(m[0xA500:0xA502]) == b"\xfd\x7c"
    m[0xA500:0xA502] = b"\xff\x22"
    return bytes(m)

if __name__ == "__main__":
    stock = fwtools.load(sys.argv[1])
    out = build(stock)
    fwtools.save_hex(sys.argv[2], out)
    d = [i for i in range(fwtools.APP_END) if stock[i] != out[i]]
    print(len(d), "bytes differ from the input; sha256 of app region:", fwtools.sha256_app(bytearray(out)))
