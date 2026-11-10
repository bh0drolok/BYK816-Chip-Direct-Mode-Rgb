# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
import sys,collections
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim51 import CPU
class FW(CPU):
    FORCE={0xBC:0x04,0x88:0x10|0x20|0x80|0x02|0x08}   # PLL ready, timer flags set
    def rs(self,a):
        v=self.sfr.get(a,0)
        f=self.FORCE.get(a)
        return v|f if f else v
def boot(img,limit,stub=None,log=None):
    c=FW(img[:0xF000]+bytes(0x1000)); c.pc=0
    hist=collections.Counter(); n=0
    while n<limit:
        c.step(); n+=1
        if n>limit-200000: hist[c.pc>>4]+=1
    return c,hist
if __name__=="__main__":
    mem=open(sys.argv[1],"rb").read()
    c,h=boot(mem,int(sys.argv[2]))
    print("pc",hex(c.pc))
    for k,v in h.most_common(10): print(hex(k<<4),v)
