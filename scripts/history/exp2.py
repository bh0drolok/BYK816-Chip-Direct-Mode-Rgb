# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
import sys
sys.path.insert(0,".")
from tick_sim import *
img=open("../patch/v720_stream4.bin","rb").read()
def tick(c,cap=1_500_000):
    c.iram[0x2B]=1; k=0
    while k<cap:
        c.step(); k+=1
        if c.pc==0x5C32: break
    return k
def summ(c):
    l=live(c); R=sum(1 for i in range(0,len(l),3) if l[i]); G=sum(1 for i in range(1,len(l),3) if l[i]); B=sum(1 for i in range(2,len(l),3) if l[i])
    return "R%3d G%3d B%3d"%(R,G,B)
def scenario(eff):
    c=FW(img[:0xF000]+bytes(0x1000)); c.pc=0
    n=0
    while c.pc!=0x5C32 and n<3_000_000: c.step(); n+=1
    c.iram[0x62]=eff; c.bset(0x39,1)      # force re-init into this effect id
    for t in range(6): tick(c)
    print("eff",hex(eff),"steady: 0512=%02x 20.1=%d 20.2=%d"%(c.xram[0x512],c.bget(0x01),c.bget(0x02)),summ(c))
    # write a flash-like painting into staging: green plane full
    st=bytearray(0x400)
    for i in range(0x84): st[0x84+i]=0xFF
    st[0x318:0x31C]=b"RTV2"
    c.xram[0x05D1:0x05D1+0x400]=st
    c.bset(0x01,1); c.bset(0x39,1)
    for t in range(8):
        tick(c); print("  tick",t,summ(c),"0512=%02x 20.1=%d 20.2=%d"%(c.xram[0x512],c.bget(0x01),c.bget(0x02)))
for e in (0x24,0x28): scenario(e)
