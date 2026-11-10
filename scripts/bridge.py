# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
"""bridge.py - OpenRGB -> Rapoo V720 bridge. OpenRGB sends E1.31 (sACN) to 127.0.0.1; this forwards each LED n to key n.
Run:  python bridge.py [universe=1] [max_reports_per_sec=800]   (keep it running; Ctrl+C to stop and blank the keys)"""
import socket, struct, sys, time
from rt4 import open_dev, setkey, VALID
RATE = float(sys.argv[2]) if len(sys.argv) > 2 else 800.0   # max reports per second sent to the keyboard (lower = fewer missed key presses)
LEDS = 132; UNIVERSE = int(sys.argv[1]) if len(sys.argv) > 1 else 1; START = 1   # start channel 1
def parse(pkt):
    """-> (universe, dmx bytes) or None. E1.31 root layer 38 + framing 77 + DMP header 10; start code at 125."""
    if len(pkt) < 126 or pkt[4:16] != b"ASC-E1.17\x00\x00\x00": return None
    uni = struct.unpack(">H", pkt[113:115])[0]
    cnt = struct.unpack(">H", pkt[123:125])[0]
    return uni, pkt[126:125 + cnt]
_next = [0.0]
def paced(h, i, c):
    now = time.perf_counter()
    if now < _next[0]:
        while time.perf_counter() < _next[0]: pass
    _next[0] = max(now, _next[0]) + 1.0 / RATE
    setkey(h, i, *c)
def main():
    h = open_dev()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 5568)); s.settimeout(0.5)
    try:                                         # also accept multicast, harmless if it fails
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                     socket.inet_aton("239.255.0.%d" % (UNIVERSE & 255)) + socket.inet_aton("0.0.0.0"))
    except OSError: pass
    last = {}; frames = sent = 0; t0 = time.time()
    print("listening on UDP 5568, universe %d - set the OpenRGB E1.31 device to 127.0.0.1" % UNIVERSE)
    try:
        while True:
            try: pkt = s.recv(2048)
            except socket.timeout: continue
            s.setblocking(False)                 # drain: keep only the newest frame
            while True:
                try: pkt = s.recv(2048)
                except (BlockingIOError, OSError): break
            s.settimeout(0.5)
            r = parse(pkt)
            if not r or r[0] != UNIVERSE: continue
            d = r[1]; frames += 1
            for i in VALID:
                o = (START - 1) + i * 3
                if o + 3 > len(d): continue
                c = (d[o], d[o + 1], d[o + 2])
                if last.get(i) != c: paced(h, i, c); last[i] = c; sent += 1
            if frames % 60 == 0: print("%.1f frames/s, %d key updates sent" % (frames / (time.time() - t0), sent), end="\r")
    except KeyboardInterrupt:
        for i in VALID: setkey(h, i, 0, 0, 0)
if __name__ == "__main__": main()
