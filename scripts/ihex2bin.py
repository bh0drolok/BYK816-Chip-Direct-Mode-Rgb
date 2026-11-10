# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
import sys, hashlib
src, dst = sys.argv[1], sys.argv[2]
mem = bytearray(b"\xff" * 0x10000)
base = 0
bad = 0
n = 0
for line in open(src):
    line = line.strip()
    if not line:
        continue
    raw = bytes.fromhex(line[1:])
    if sum(raw) & 0xFF:
        bad += 1
    cnt, addr, typ = raw[0], (raw[1] << 8) | raw[2], raw[3]
    if typ == 0:
        mem[base + addr: base + addr + cnt] = raw[4:4 + cnt]
        n += 1
    elif typ == 1:
        break
open(dst, "wb").write(bytes(mem))
print("data records", n, "bad checksums", bad, "md5", hashlib.md5(mem).hexdigest())
