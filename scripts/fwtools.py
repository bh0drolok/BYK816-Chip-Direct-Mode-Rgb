"""fwtools.py - Intel HEX / raw binary load + save helpers (firmware-only region)."""
# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
import hashlib

APP_END = 0xF000            # app region is 0x0000-0xEFFF; 0xF000+ is the ISP boot loader and is never part of a patched image
IMG_SIZE = 0x10000


def load(path):
    """Return a 64 KiB bytearray. Unwritten bytes are 0xFF. Accepts .hex/.ihx (Intel HEX) or raw .bin."""
    data = open(path, "rb").read()
    if data[:1] == b":":
        mem = bytearray(b"\xff" * IMG_SIZE)
        seen = bytearray(IMG_SIZE)
        base = 0
        for ln, line in enumerate(data.decode("ascii", "replace").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            if not line.startswith(":"):
                raise ValueError("line %d: not an Intel HEX record" % ln)
            raw = bytes.fromhex(line[1:])
            if sum(raw) & 0xFF:
                raise ValueError("line %d: bad checksum" % ln)
            n, addr, typ = raw[0], (raw[1] << 8) | raw[2], raw[3]
            if len(raw) != n + 5:
                raise ValueError("line %d: bad length" % ln)
            if typ == 0:
                a = base + addr
                if a + n > IMG_SIZE:
                    raise ValueError("line %d: data beyond 64 KiB" % ln)
                mem[a:a + n] = raw[4:4 + n]
                seen[a:a + n] = b"\x01" * n
            elif typ == 4:
                base = ((raw[4] << 8) | raw[5]) << 16
            elif typ == 1:
                break
        return mem
    if len(data) > IMG_SIZE:
        raise ValueError("binary larger than 64 KiB")
    mem = bytearray(b"\xff" * IMG_SIZE)
    mem[:len(data)] = data
    return mem


def save_hex(path, mem, end=APP_END):
    """Write the firmware-only Intel HEX (0x0000..end-1), 16-byte records, CRLF line endings."""
    out = []
    for a in range(0, end, 16):
        ch = bytes(mem[a:a + 16])
        r = bytes([len(ch), a >> 8, a & 0xFF, 0]) + ch
        out.append(":" + (r + bytes([(-sum(r)) & 0xFF])).hex().upper())
    out.append(":00000001FF")
    with open(path, "w", newline="") as f:
        f.write("\r\n".join(out) + "\r\n")


def sha256_app(mem):
    return hashlib.sha256(bytes(mem[:APP_END])).hexdigest()


def sha256_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()
