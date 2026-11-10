# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
import sys,collections
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from boot_sim import FW
def live(c):  # 6 rows x 22 cols x3 at 0x0386+row*0x42+col*3
    return bytes(c.xram[0x0386:0x0512])
def run_ticks(c,ticks,per_tick_limit=400000,watch=False):
    log=[]
    for t in range(ticks):
        # wait at main-loop head, then raise tick flag
        n=0
        while c.pc!=0x5C32 and n<per_tick_limit:
            c.step(); n+=1
        c.iram[0x2B]=1
        before=live(c)
        n=0
        while n<per_tick_limit:
            c.step(); n+=1
            if c.pc==0x5C32 and n>5: break
            if watch and n%2000==0:
                log.append((t,n,live(c)))
        log.append((t,"end",live(c)))
    return log
if __name__=="__main__":
    mem=open(sys.argv[1],"rb").read()
    c=FW(mem[:0xF000]+bytes(0x1000)); c.pc=0
    n=0
    while c.pc!=0x5C32 and n<3_000_000: c.step(); n+=1
    print("reached main head after",n,"steps")
    log=run_ticks(c,6)
    print("0512=%02x 20.1=%d 20.2=%d 24.4=%d 27.1=%d"%(c.xram[0x512],c.bget(0x01),c.bget(0x02),c.bget(0x24),c.bget(0x39)))
    lv=live(c); print("live nonzero bytes:",sum(1 for b in lv if b), "first key rgb",lv[:3].hex(), lv[3:6].hex())
