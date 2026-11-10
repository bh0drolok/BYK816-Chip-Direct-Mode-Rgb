# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
"""rt3.py - streaming test for the v3 'stream' firmware (frames stay in RAM when tagged RTV2).
Put next to kb.py.  Modes: static R G B | sweep | rainbow"""
import sys, time, colorsys, hid
from kb import paths

VALID = ([0] + list(range(2, 6)) + list(range(7, 18)) + list(range(22, 35)) +
         list(range(36, 58)) + list(range(59, 78)) + [79, 84, 85, 86, 88] +
         list(range(90, 100)) + [102, 104] + list(range(106, 113)) +
         [115, 118, 119, 120, 122, 125, 126, 127, 128, 130])
HDR = bytes.fromhex("0609ac0040000000")
TAG = b"RTV2"
TAG_AT = 8 + 0x318          # payload offset 0x318 of the 0xAC page

def frame(colors):
    b = bytearray(1032)
    b[:8] = HDR
    for i, (r, g, bl) in colors.items():
        b[8 + i] = bl
        b[140 + i] = g
        b[272 + i] = r
    b[TAG_AT:TAG_AT + 4] = TAG
    return bytes(b)

def open_dev():
    probe = list(frame({}))
    probe[1] = 0xFF            # harmless unused type: the probe must not repaint or blank the keyboard
    for p in paths():
        h = hid.device()
        try:
            h.open_path(p)
            if h.send_feature_report(probe) > 0:
                return h
        except Exception:
            pass
        try:
            h.close()
        except Exception:
            pass
    sys.exit("could not open the keyboard (is the Rapoo software closed?)")

if __name__ == "__main__":
    mode = sys.argv[1]
    h = open_dev()
    push = lambda cols: h.send_feature_report(list(frame(cols)))
    if mode == "static":
        r, g, b = map(int, sys.argv[2:5])
        push({i: (r, g, b) for i in VALID})
    elif mode == "sweep":
        for i in VALID:
            push({i: (255, 255, 255)})
            print(i, "row,col =", divmod(i, 22))
            time.sleep(0.08)
    elif mode == "hold":
        # same colour repeated: python rt3.py hold R G B [fps] [seconds]
        r, g, b = map(int, sys.argv[2:5])
        fps = float(sys.argv[5]) if len(sys.argv) > 5 else 20.0
        secs = float(sys.argv[6]) if len(sys.argv) > 6 else 6.0
        t0 = time.time(); n = 0
        while time.time() - t0 < secs:
            push({i: (r, g, b) for i in VALID}); n += 1
            time.sleep(1.0 / fps)
        print(f"sent {n} identical frames")
    elif mode == "slow":
        # python rt3.py slow [gap_seconds] [count]: alternate red / blue, one frame per gap
        gap = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
        cnt = int(sys.argv[3]) if len(sys.argv) > 3 else 6
        for k in range(cnt):
            c = (255, 0, 0) if k % 2 == 0 else (0, 0, 255)
            push({i: c for i in VALID})
            print(k, "red" if k % 2 == 0 else "blue", time.strftime("%H:%M:%S"))
            time.sleep(gap)
    elif mode == "noop":
        # reception-only test: python rt3.py noop [fps] [seconds]
        # sends full-size 06 reports with an UNUSED type (0xFF): the firmware receives them and ignores them.
        fps = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
        secs = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
        b = bytearray(1032); b[:8] = bytes.fromhex("06ffac0040000000")
        t0 = time.time(); n = 0
        while time.time() - t0 < secs:
            h.send_feature_report(list(b)); n += 1
            time.sleep(1.0 / fps)
        print(f"sent {n} no-op reports")
    elif mode == "ping":
        # 6-byte sync report only, sent on whichever HID path really accepts it:
        #   python rt3.py ping [fps (0 = as fast as possible)] [seconds]
        fps = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
        secs = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
        sync = [0x05, 0x83, 0, 0, 0, 0]
        hp = None
        for p in paths():
            hh = hid.device()
            try:
                hh.open_path(p)
                if hh.send_feature_report(sync) > 0:
                    hp = hh; break
            except Exception:
                pass
            try:
                hh.close()
            except Exception:
                pass
        if hp is None:
            sys.exit("no HID path accepts the 6-byte sync report")
        t0 = time.time(); ok = bad = 0
        while time.time() - t0 < secs:
            try:
                r = hp.send_feature_report(sync)
            except Exception:
                r = -1
            if r > 0: ok += 1
            else: bad += 1
            if fps > 0:
                time.sleep(1.0 / fps)
        print(f"accepted {ok}, failed {bad} -> {ok / secs:.0f} accepted per second")
    elif mode == "rainbow":
        fps = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
        secs = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
        period = 1.0 / fps
        t0 = time.time(); n = 0; worst = 0; nxt = t0
        while (t := time.time() - t0) < secs:
            cols = {i: tuple(int(255 * c) for c in
                    colorsys.hsv_to_rgb(((i % 22) / 22 + t * 0.5) % 1, 1, 1))
                    for i in VALID}
            s = time.time(); push(cols); worst = max(worst, time.time() - s); n += 1
            nxt += period
            d = nxt - time.time()
            if d > 0:
                time.sleep(d)          # idle gap: lets the keyboard render and scan keys
            else:
                nxt = time.time()
        print(f"{n / secs:.1f} fps (target {fps}), slowest send {worst * 1000:.0f} ms")
