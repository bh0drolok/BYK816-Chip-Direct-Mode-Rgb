# NOTE: guideline, not an exact or supported tool. Tiny helper used by rt4.py / bridge.py / viz.py / history/rt3.py.
"""kb.py - list HID paths of the Rapoo V720 (VID 0x24AE, PID 0x4018). Needs: pip install hidapi"""
import hid
VID, PID = 0x24AE, 0x4018

def paths():
    """All HID interface paths of the keyboard. The tools try each one until a 6-byte feature report is accepted."""
    return [d["path"] for d in hid.enumerate(VID, PID)]
