# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
"""rt4.py - tiny-report sender for the v6 firmware (05 E0 idx R G B, one key per 6-byte report).
Put next to kb.py.  python rt4.py static R G B | rainbow [secs] | benchmark [secs]"""
import sys, time, colorsys, hid
from kb import paths
VALID = ([0] + list(range(2, 6)) + list(range(7, 18)) + list(range(22, 35)) +
         list(range(36, 58)) + list(range(59, 78)) + [79, 84, 85, 86, 88] +
         list(range(90, 100)) + [102, 104] + list(range(106, 113)) +
         [115, 118, 119, 120, 122, 125, 126, 127, 128, 130])
def open_dev():
    for p in paths():
        h = hid.device()
        try:
            h.open_path(p)
            if h.send_feature_report([5, 0x83, 0, 0, 0, 0]) > 0: return h
        except Exception: pass
        try: h.close()
        except Exception: pass
    sys.exit("no HID path accepts 6-byte reports")
def setkey(h, i, r, g, b): return h.send_feature_report([5, 0xE0, i, r, g, b])
def main():
    h = open_dev(); m = sys.argv[1] if len(sys.argv) > 1 else "static"
    if m == "static":
        r, g, b = (int(x) for x in sys.argv[2:5])
        for i in VALID: setkey(h, i, r, g, b)
    elif m in ("rainbow", "benchmark"):
        secs = float(sys.argv[2]) if len(sys.argv) > 2 else 8.0
        t0 = time.time(); frames = sent = 0
        while time.time() - t0 < secs:
            ph = (time.time() - t0) * 0.5
            for n, i in enumerate(VALID):
                c = colorsys.hsv_to_rgb((ph + n / len(VALID)) % 1.0, 1, 1)
                setkey(h, i, *(int(x * 255) for x in c)); sent += 1
            frames += 1
        print(f"{frames} full frames, {sent} reports in {secs:.0f}s -> {frames/secs:.1f} fps")
if __name__ == "__main__":
    main()
